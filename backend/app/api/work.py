from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.utils import get_actor_employee_id, log_activity
from app.db.session import get_session
from app.integrations.notify import NotifyContext, notify_openclaw
from app.integrations.openclaw import OpenClawClient
from app.models.org import Employee
from app.models.work import Task, TaskComment
from app.schemas.work import TaskCommentCreate, TaskCreate, TaskReviewDecision, TaskUpdate

logger = logging.getLogger("app.work")

router = APIRouter(tags=["work"])

ALLOWED_STATUSES = {"backlog", "ready", "in_progress", "review", "done", "blocked"}


def _validate_task_assignee(session: Session, assignee_employee_id: int) -> None:
    """Enforce that only provisioned agents can be assigned tasks.

    Humans can be assigned regardless.
    Agents must be active, notify_enabled, and have openclaw_session_key.
    """

    emp = session.get(Employee, assignee_employee_id)
    if emp is None:
        raise HTTPException(status_code=400, detail="Assignee employee not found")

    if emp.employee_type == "agent":
        if emp.status != "active":
            raise HTTPException(status_code=400, detail="Cannot assign task to inactive agent")
        if not emp.notify_enabled:
            raise HTTPException(
                status_code=400, detail="Cannot assign task to agent with notifications disabled"
            )
        if not emp.openclaw_session_key:
            raise HTTPException(status_code=400, detail="Cannot assign task to unprovisioned agent")


@router.get("/tasks", response_model=list[Task])
def list_tasks(project_id: int | None = None, session: Session = Depends(get_session)):
    stmt = select(Task).order_by(Task.id.asc())
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    return session.exec(stmt).all()


@router.post("/tasks", response_model=Task)
def create_task(
    payload: TaskCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    if payload.created_by_employee_id is None:
        payload = TaskCreate(
            **{**payload.model_dump(), "created_by_employee_id": actor_employee_id}
        )

    if payload.assignee_employee_id is not None:
        _validate_task_assignee(session, payload.assignee_employee_id)

    # Default reviewer to the manager of the assignee (if not explicitly provided).
    if payload.reviewer_employee_id is None and payload.assignee_employee_id is not None:
        assignee = session.get(Employee, payload.assignee_employee_id)
        if assignee is not None and assignee.manager_id is not None:
            payload = TaskCreate(
                **{**payload.model_dump(), "reviewer_employee_id": assignee.manager_id}
            )

    task = Task(**payload.model_dump())
    if task.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    task.updated_at = datetime.utcnow()
    session.add(task)

    try:
        session.flush()
        log_activity(
            session,
            actor_employee_id=actor_employee_id,
            entity_type="task",
            entity_id=task.id,
            verb="created",
            payload={"project_id": task.project_id, "title": task.title},
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Task create violates constraints")

    session.refresh(task)
    background.add_task(
        notify_openclaw,
        NotifyContext(event="task.created", actor_employee_id=actor_employee_id, task_id=task.id),
    )
    # Explicitly return a serializable payload (guards against empty {} responses)
    return Task.model_validate(task)


@router.post("/tasks/{task_id}/dispatch")
def dispatch_task(
    task_id: int,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    logger.info("dispatch_task: called", extra={"task_id": task_id, "actor": actor_employee_id})
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(
        "dispatch_task: loaded",
        extra={
            "task_id": getattr(task, "id", None),
            "assignee_employee_id": getattr(task, "assignee_employee_id", None),
        },
    )

    if task.assignee_employee_id is None:
        raise HTTPException(status_code=400, detail="Task has no assignee")

    _validate_task_assignee(session, task.assignee_employee_id)

    client = OpenClawClient.from_env()
    if client is None:
        logger.warning("dispatch_task: missing OpenClaw env")
        raise HTTPException(
            status_code=503,
            detail="OpenClaw gateway is not configured (set OPENCLAW_GATEWAY_URL/TOKEN)",
        )

    # Best-effort: enqueue an agent dispatch. This does not mutate the task.
    background.add_task(
        notify_openclaw,
        NotifyContext(event="task.assigned", actor_employee_id=actor_employee_id, task_id=task.id),
    )

    return {"ok": True}


def _require_reviewer_comment(body: str | None) -> str:
    if body is None or not body.strip():
        raise HTTPException(status_code=400, detail="Reviewer must provide a comment for audit")
    return body.strip()


@router.post("/tasks/{task_id}/review", response_model=Task)
def review_task(
    task_id: int,
    payload: TaskReviewDecision,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    """Reviewer approves or requests changes.

    - Approve => status=done
    - Changes => status=in_progress

    Always writes a TaskComment by the reviewer for audit.
    """

    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.reviewer_employee_id is None:
        raise HTTPException(status_code=400, detail="Task has no reviewer")

    if actor_employee_id != task.reviewer_employee_id:
        raise HTTPException(status_code=403, detail="Only the reviewer can approve/request changes")

    decision = (payload.decision or "").strip().lower()
    if decision not in {"approve", "changes"}:
        raise HTTPException(status_code=400, detail="Invalid decision")

    comment_body = _require_reviewer_comment(payload.comment_body)

    new_status = "done" if decision == "approve" else "in_progress"

    before_status = task.status
    task.status = new_status
    task.updated_at = datetime.utcnow()
    session.add(task)

    c = TaskComment(task_id=task.id, author_employee_id=actor_employee_id, body=comment_body)
    session.add(c)

    try:
        session.flush()
        log_activity(
            session,
            actor_employee_id=actor_employee_id,
            entity_type="task",
            entity_id=task.id,
            verb="reviewed",
            payload={"decision": decision, "status": new_status},
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Review action violates constraints")

    session.refresh(task)
    session.refresh(c)

    # Notify assignee (comment.created will exclude author)
    background.add_task(
        notify_openclaw,
        session,
        NotifyContext(
            event="comment.created", actor_employee_id=actor_employee_id, task=task, comment=c
        ),
    )

    # Notify reviewer/PMs about status change
    if before_status != task.status:
        background.add_task(
            notify_openclaw,
            NotifyContext(
                event="status.changed",
                actor_employee_id=actor_employee_id,
                task_id=task.id,
                changed_fields={"status": {"from": before_status, "to": task.status}},
            ),
        )

    return Task.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    logger.info("dispatch_task: called", extra={"task_id": task_id, "actor": actor_employee_id})
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    before = {
        "assignee_employee_id": task.assignee_employee_id,
        "reviewer_employee_id": task.reviewer_employee_id,
        "status": task.status,
    }

    data = payload.model_dump(exclude_unset=True)
    if "assignee_employee_id" in data and data["assignee_employee_id"] is not None:
        _validate_task_assignee(session, data["assignee_employee_id"])
    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Enforce review workflow: agent assignees cannot mark tasks done directly.
    if data.get("status") == "done":
        assignee = (
            session.get(Employee, task.assignee_employee_id) if task.assignee_employee_id else None
        )
        if assignee is not None and assignee.employee_type == "agent":
            if actor_employee_id == task.assignee_employee_id:
                raise HTTPException(
                    status_code=403,
                    detail="Assignee agents cannot mark tasks done; set status=review for manager approval",
                )
        if task.reviewer_employee_id is not None and actor_employee_id != task.reviewer_employee_id:
            raise HTTPException(status_code=403, detail="Only the reviewer can mark a task done")

    # If a task is sent to review and no reviewer is set, default reviewer to assignee's manager.
    if (
        data.get("status") in {"review", "ready_for_review"}
        and data.get("reviewer_employee_id") is None
    ):
        assignee_id = data.get("assignee_employee_id", task.assignee_employee_id)
        if assignee_id is not None:
            assignee = session.get(Employee, assignee_id)
            if assignee is not None and assignee.manager_id is not None:
                data["reviewer_employee_id"] = assignee.manager_id

    for k, v in data.items():
        setattr(task, k, v)
    task.updated_at = datetime.utcnow()
    session.add(task)

    try:
        session.flush()
        log_activity(
            session,
            actor_employee_id=actor_employee_id,
            entity_type="task",
            entity_id=task.id,
            verb="updated",
            payload=data,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Task update violates constraints")

    session.refresh(task)

    # notify based on meaningful changes
    changed = {}
    if before.get("assignee_employee_id") != task.assignee_employee_id:
        changed["assignee_employee_id"] = {
            "from": before.get("assignee_employee_id"),
            "to": task.assignee_employee_id,
        }
        background.add_task(
            notify_openclaw,
            NotifyContext(
                event="task.assigned",
                actor_employee_id=actor_employee_id,
                task_id=task.id,
                changed_fields=changed,
            ),
        )
    if before.get("status") != task.status:
        changed["status"] = {"from": before.get("status"), "to": task.status}
        background.add_task(
            notify_openclaw,
            NotifyContext(
                event="status.changed",
                actor_employee_id=actor_employee_id,
                task_id=task.id,
                changed_fields=changed,
            ),
        )
    if not changed and data:
        background.add_task(
            notify_openclaw,
            NotifyContext(
                event="task.updated",
                actor_employee_id=actor_employee_id,
                task_id=task.id,
                changed_fields=data,
            ),
        )

    return Task.model_validate(task)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    logger.info("dispatch_task: called", extra={"task_id": task_id, "actor": actor_employee_id})
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(task)
    try:
        session.flush()
        log_activity(
            session,
            actor_employee_id=actor_employee_id,
            entity_type="task",
            entity_id=task_id,
            verb="deleted",
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Task delete violates constraints")

    return {"ok": True}


@router.get("/task-comments", response_model=list[TaskComment])
def list_task_comments(task_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.id.asc())
    ).all()


@router.post("/task-comments", response_model=TaskComment)
def create_task_comment(
    payload: TaskCommentCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    actor_employee_id: int = Depends(get_actor_employee_id),
):
    if payload.author_employee_id is None:
        payload = TaskCommentCreate(
            **{**payload.model_dump(), "author_employee_id": actor_employee_id}
        )

    c = TaskComment(**payload.model_dump())
    session.add(c)

    try:
        session.flush()
        log_activity(
            session,
            actor_employee_id=actor_employee_id,
            entity_type="task",
            entity_id=c.task_id,
            verb="commented",
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Comment create violates constraints")

    session.refresh(c)
    task = session.get(Task, c.task_id)
    if task is not None:
        background.add_task(
            notify_openclaw,
            NotifyContext(
                event="comment.created",
                actor_employee_id=actor_employee_id,
                task_id=task.id,
                comment_id=c.id,
            ),
        )
    return TaskComment.model_validate(c)

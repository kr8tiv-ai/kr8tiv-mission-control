# Cloudflare Tunnel Setup

Secure HTTPS access to your infrastructure without exposing ports.

---

## Why Cloudflare Tunnel?

**Without Tunnel:**
- Ports exposed directly to internet (security risk)
- Must manage SSL certificates manually
- Vulnerable to port scans and DDoS
- IP address visible

**With Tunnel:**
- ✅ No exposed ports (all traffic through Cloudflare)
- ✅ Automatic HTTPS with valid certificates
- ✅ DDoS protection included
- ✅ Hide origin IP address
- ✅ Access control & authentication built-in

---

## Prerequisites

1. Domain name (e.g., `kr8tiv.ai`)
2. Cloudflare account (free tier works)
3. Domain DNS managed by Cloudflare

---

## Installation

### 1. Install cloudflared

```bash
# Download latest version
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64

# Install
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Verify
cloudflared --version
```

### 2. Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser window. Select your domain and authorize.

### 3. Create Tunnels

Create a tunnel for each service you want to expose:

```bash
# Create tunnel
cloudflared tunnel create friday

# Note the tunnel ID from output
# Example: Created tunnel friday with id abc123def456
```

Repeat for each service (arsenal, edith, mission-control, etc.)

---

## Configuration

### Create config file

```bash
sudo mkdir -p /etc/cloudflared
sudo nano /etc/cloudflared/config.yml
```

**Example config:**

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  # Friday agent
  - hostname: friday.kr8tiv.ai
    service: http://localhost:48650
  
  # Arsenal agent
  - hostname: arsenal.kr8tiv.ai
    service: http://localhost:48652
  
  # Mission Control frontend
  - hostname: mission.kr8tiv.ai
    service: http://localhost:3100
  
  # Uptime Kuma (monitoring)
  - hostname: monitor.kr8tiv.ai
    service: http://localhost:3001
  
  # Dozzle (logs)
  - hostname: logs.kr8tiv.ai
    service: http://localhost:9999
  
  # Catch-all (required)
  - service: http_status:404
```

---

## DNS Configuration

### Route traffic through tunnel

```bash
# For each service:
cloudflared tunnel route dns YOUR_TUNNEL_ID friday.kr8tiv.ai
cloudflared tunnel route dns YOUR_TUNNEL_ID arsenal.kr8tiv.ai
cloudflared tunnel route dns YOUR_TUNNEL_ID mission.kr8tiv.ai
# etc.
```

This creates CNAME records in Cloudflare DNS automatically.

---

## Running the Tunnel

### Test run (foreground)

```bash
cloudflared tunnel run YOUR_TUNNEL_ID
```

### Run as service (background)

```bash
# Install as system service
sudo cloudflared service install

# Start service
sudo systemctl start cloudflared

# Enable on boot
sudo systemctl enable cloudflared

# Check status
sudo systemctl status cloudflared
```

---

## Access Control (Optional)

Protect sensitive endpoints with authentication:

### In Cloudflare Dashboard:

1. Go to Zero Trust > Access > Applications
2. Click "Add an application"
3. Choose "Self-hosted"
4. Configure:
   - Application name: "Uptime Kuma"
   - Subdomain: `monitor`
   - Domain: `kr8tiv.ai`
5. Add policy:
   - Policy name: "Admin only"
   - Action: Allow
   - Rules: Email is `your@email.com`
6. Save

Now `monitor.kr8tiv.ai` requires authentication before access.

---

## Troubleshooting

### Tunnel not connecting

```bash
# Check service status
sudo systemctl status cloudflared

# View logs
sudo journalctl -u cloudflared -f

# Test config
cloudflared tunnel ingress validate
```

### DNS not resolving

```bash
# Check DNS records in Cloudflare dashboard
# Ensure CNAME records point to tunnel ID

# Test resolution
nslookup friday.kr8tiv.ai
```

### 502 Bad Gateway

- Check that local service is running: `curl http://localhost:PORT`
- Verify port in config matches actual service port
- Check firewall isn't blocking localhost connections

---

## Security Best Practices

✅ **Enable Access policies** for sensitive endpoints (Uptime Kuma, Dozzle)  
✅ **Use separate tunnels** for production vs staging  
✅ **Rotate tunnel credentials** quarterly  
✅ **Monitor tunnel logs** for suspicious activity  
✅ **Enable Cloudflare WAF** for additional protection  

❌ **Don't** expose admin panels publicly without authentication  
❌ **Don't** use same tunnel for multiple domains  
❌ **Don't** hardcode credentials in config files (use service install)  

---

## Cost

Cloudflare Tunnel is **free** for most use cases.

Paid features (optional):
- Zero Trust Access (authentication): $7/user/month
- Advanced WAF rules: $20/month

---

## Migration from Direct Port Exposure

### Before migration:
1. Test tunnel setup on a non-production subdomain
2. Verify all services accessible via tunnel
3. Document current port mappings

### During migration:
1. Update application URLs to use tunnel hostnames
2. Configure firewalls to block direct port access
3. Monitor for any connection issues

### After migration:
1. Remove port forwarding rules
2. Close ports in UFW firewall
3. Update documentation with new URLs

---

## Questions?

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [KR8TIV Support](https://kr8tiv.ai/contact)

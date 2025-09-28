# Electronics HAL - Docker Deployment

This directory contains Docker configuration files for deploying the Electronics HAL system in containerized environments.

## Quick Start

### Basic Deployment

```bash
# Build and start the basic HAL system
docker-compose up -d electronics-hal

# Start with monitoring dashboard
docker-compose up -d electronics-hal hal-dashboard

# Start complete monitoring stack
docker-compose up -d
```

### Access Points

- **HAL Dashboard**: http://localhost:5000
- **Grafana**: http://localhost:3000 (admin/hal-admin)
- **Prometheus**: http://localhost:9090
- **Main Application**: Container `electronics-hal-app`

## Services

### Core Services

#### electronics-hal
- Main HAL application container
- Runs instrument control and test execution
- Mounts USB devices for real instrument access
- Persistent data storage via volumes

#### hal-dashboard
- Real-time monitoring web interface
- WebSocket-based live updates
- REST API for metrics access
- Built-in instrument status monitoring

### Optional Services

#### redis
- Caching and pub/sub messaging
- Used for inter-service communication
- Persistent data storage

#### prometheus
- Metrics collection and storage
- Time-series database for monitoring
- Configurable retention period

#### grafana
- Advanced data visualization
- Pre-configured dashboards
- Alert management

#### nginx
- Reverse proxy for web services
- SSL termination
- Load balancing

## Configuration

### Environment Variables

#### HAL Application
```bash
HAL_CONFIG_FILE=/app/config/hal_config.yml
HAL_LOG_LEVEL=INFO|DEBUG|WARNING|ERROR
PYTHONPATH=/app
```

#### Dashboard
```bash
HAL_DASHBOARD_HOST=0.0.0.0
HAL_DASHBOARD_PORT=5000
HAL_DASHBOARD_DEBUG=false
```

### Volume Mounts

#### Persistent Data
- `hal-logs`: Application logs
- `hal-reports`: Test reports and results
- `hal-test-data`: Test data and measurements
- `hal-monitoring`: Monitoring metrics
- `hal-simulation`: Simulation data

#### Configuration
- `./config:/app/config:ro`: Configuration files
- `./docker/prometheus.yml`: Prometheus configuration
- `./docker/grafana/`: Grafana dashboards and datasources

#### Hardware Access
- `/dev/bus/usb:/dev/bus/usb`: USB device access for instruments

## Development Mode

### Local Development with Docker

```bash
# Development compose with code mounting
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f electronics-hal

# Execute commands in container
docker-compose exec electronics-hal python -m hal.cli --help

# Run tests in container
docker-compose exec electronics-hal python -m pytest
```

### Custom Configuration

Create local configuration files:

```bash
mkdir -p config
cp hal/config/default_config.yml config/hal_config.yml
# Edit config/hal_config.yml as needed
```

## Production Deployment

### Production Stack

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Enable monitoring and alerting
docker-compose up -d prometheus grafana

# Set up reverse proxy
docker-compose up -d nginx
```

### Security Considerations

1. **SSL/TLS**: Configure SSL certificates in `docker/ssl/`
2. **Authentication**: Set strong passwords for Grafana
3. **Network**: Use custom bridge networks
4. **USB Access**: Limit privileged access in production
5. **Secrets**: Use Docker secrets for sensitive data

### Performance Tuning

#### Resource Limits
```yaml
# Add to service definitions
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

#### Monitoring Resources
```bash
# Monitor container resources
docker stats

# View resource usage
docker-compose exec electronics-hal top
```

## Troubleshooting

### Common Issues

#### USB Device Access
```bash
# Check USB devices
docker-compose exec electronics-hal lsusb

# Verify permissions
docker-compose exec electronics-hal ls -la /dev/bus/usb/
```

#### Service Dependencies
```bash
# Check service health
docker-compose ps

# View service logs
docker-compose logs hal-dashboard

# Restart services
docker-compose restart electronics-hal
```

#### Network Connectivity
```bash
# Test service communication
docker-compose exec electronics-hal curl hal-dashboard:5000/api/system/health

# Check network configuration
docker network ls
docker network inspect electronics-hal_hal-network
```

### Debugging

#### Development Mode
```bash
# Run with debug logging
HAL_LOG_LEVEL=DEBUG docker-compose up electronics-hal

# Interactive shell
docker-compose exec electronics-hal bash

# Python debugging
docker-compose exec electronics-hal python -i -c "import hal"
```

#### Log Analysis
```bash
# Follow application logs
docker-compose logs -f electronics-hal

# Export logs
docker-compose logs electronics-hal > hal-logs.txt

# Search logs
docker-compose logs electronics-hal | grep ERROR
```

## Backup and Recovery

### Data Backup
```bash
# Backup all volumes
docker run --rm -v electronics-hal_hal-test-data:/data -v $(pwd):/backup alpine tar czf /backup/hal-data-backup.tar.gz -C /data .

# Restore from backup
docker run --rm -v electronics-hal_hal-test-data:/data -v $(pwd):/backup alpine tar xzf /backup/hal-data-backup.tar.gz -C /data
```

### Configuration Backup
```bash
# Export configuration
cp -r config/ config-backup-$(date +%Y%m%d)/

# Export Docker configuration
docker-compose config > docker-compose-backup.yml
```

## Monitoring and Alerting

### Health Checks
```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect electronics-hal-app | jq '.[0].State.Health'
```

### Metrics Collection
- CPU, memory, network usage
- Instrument connection status
- Test execution metrics
- Error rates and latency

### Alerting Rules
- High error rates
- Instrument disconnections
- Resource exhaustion
- Service unavailability

## Scaling

### Horizontal Scaling
```yaml
# Scale services
electronics-hal:
  deploy:
    replicas: 3

# Load balancer configuration
nginx:
  depends_on:
    - electronics-hal
```

### Resource Optimization
- Use multi-stage builds for smaller images
- Implement health checks for all services
- Configure resource limits and reservations
- Use volume caching for dependencies
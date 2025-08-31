# Tax Extractor UI Suite

A self-hosted web interface for running complex tax extractors (Selenium/Playwright) with real-time Supabase synchronization.

## Features

- **Web-based Control Panel**: Modern UI for managing extraction jobs
- **Real-time Updates**: WebSocket connection for live job status
- **Job Queue System**: Concurrent extraction with configurable limits
- **Supabase Integration**: Automatic sync of extraction results
- **Multiple Extraction Methods**: Selenium, Playwright, and HTTP extractors
- **Docker Support**: Easy deployment with Docker Compose
- **Progress Tracking**: Real-time progress and status updates

## Quick Start

### Option 1: Run with Python (Development)

```bash
# Install dependencies and start
./start_extractor_ui.sh install

# Or if dependencies are already installed
./start_extractor_ui.sh
```

### Option 2: Run with Docker (Production)

```bash
# Start with Docker Compose
./start_extractor_ui.sh docker

# Or manually
docker-compose -f docker-compose.extractor.yml up -d
```

## Access the UI

Once started, access the interface at:
- **UI**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **WebSocket**: ws://localhost:8001/ws

## Configuration

Create a `.env` file with your settings:

```env
# Supabase Configuration (Required for database sync)
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# Extraction Settings
MAX_CONCURRENT_EXTRACTIONS=3
EXTRACTION_TIMEOUT=30000
HEADLESS_MODE=true

# Logging
LOG_LEVEL=info
```

## UI Features

### Control Panel
- **Extraction Types**:
  - Specific Properties: Select individual properties
  - By Entity: Extract all properties for an entity
  - By Jurisdiction: Extract all properties in a jurisdiction

- **Extraction Methods**:
  - Auto-detect: Automatically choose best method
  - Selenium: For JavaScript-heavy sites
  - Playwright: For complex single-page applications
  - HTTP: For simple HTML sites

### Job Management
- **Active Jobs**: Currently running extractions
- **Queued Jobs**: Waiting to be processed
- **Completed Jobs**: Successfully extracted with results
- **Failed Jobs**: Failed extractions with error details

### Real-time Updates
- WebSocket connection for instant updates
- Progress bars for running jobs
- System status indicators
- Extraction statistics

## API Endpoints

### Core Endpoints
- `GET /`: Web UI interface
- `GET /api/status`: System status and statistics
- `GET /api/properties`: List all properties from Supabase
- `GET /api/entities`: List all entities from Supabase
- `POST /api/extract`: Start extraction jobs
- `GET /api/jobs`: List all jobs
- `GET /api/jobs/{job_id}`: Get specific job status
- `DELETE /api/jobs/{job_id}`: Cancel a job
- `GET /api/extractions`: Recent extractions from Supabase
- `WS /ws`: WebSocket for real-time updates

### Starting Extractions

```python
import requests

# Extract specific properties
response = requests.post('http://localhost:8001/api/extract', json={
    'property_ids': ['prop-123', 'prop-456'],
    'extraction_method': 'auto',
    'save_to_supabase': True
})

# Extract by entity
response = requests.post('http://localhost:8001/api/extract', json={
    'entity_id': 'entity-789',
    'extraction_method': 'selenium'
})

# Extract by jurisdiction
response = requests.post('http://localhost:8001/api/extract', json={
    'jurisdiction': 'Harris County',
    'extraction_method': 'playwright'
})
```

## Supported Jurisdictions

### Selenium-based (Complex JavaScript)
- Maricopa County, AZ
- Harris County, TX
- Wayne County, NC
- Johnston County, NC

### Playwright-based (SPA sites)
- Craven County, NC
- Wilson County, NC
- Vance County, NC

### HTTP-based (Simple HTML)
- Montgomery County, TX
- Fort Bend County, TX
- Chambers County, TX
- Galveston County, TX
- Walker County, TX
- Liberty County, TX

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│   Web UI (HTML) │────▶│  FastAPI     │────▶│   Supabase   │
│   + JavaScript  │◀────│  WebSocket   │◀────│   Database   │
└─────────────────┘     └──────────────┘     └──────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  Job Queue       │
                    │  (Threading)     │
                    └──────────────────┘
                               │
                    ┌──────────┴────────────┐
                    ▼                        ▼
            ┌──────────────┐        ┌──────────────┐
            │   Selenium   │        │  Playwright  │
            │  Extractors  │        │  Extractors  │
            └──────────────┘        └──────────────┘
```

## Docker Deployment

### Build and Run
```bash
# Build image
docker build -f Dockerfile.extractor -t tax-extractor-ui .

# Run with docker-compose
docker-compose -f docker-compose.extractor.yml up -d

# View logs
docker-compose -f docker-compose.extractor.yml logs -f

# Stop services
docker-compose -f docker-compose.extractor.yml down
```

### Docker Services
- **tax-extractor-ui**: Main application (port 8001)
- **redis**: Job queue persistence (optional, port 6379)
- **postgres**: Local database (optional, port 5432)
- **nginx**: Reverse proxy (optional, ports 80/443)

## Monitoring

### View Logs
```bash
# Application logs
tail -f logs/extractor_ui_service.log

# Docker logs
docker-compose -f docker-compose.extractor.yml logs -f tax-extractor-ui
```

### System Status
- Active jobs count
- Queued jobs count
- Completed today
- Average extraction time
- Extractor availability
- Supabase connection status

## Troubleshooting

### Common Issues

1. **Chrome/Chromium not found**
   ```bash
   # Install Chrome
   wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
   apt-get update && apt-get install -y google-chrome-stable
   ```

2. **Playwright browsers missing**
   ```bash
   playwright install chromium
   playwright install-deps
   ```

3. **Supabase connection failed**
   - Check SUPABASE_URL and SUPABASE_ANON_KEY in .env
   - Verify network connectivity
   - Check Supabase service status

4. **Jobs stuck in queue**
   - Check MAX_CONCURRENT_EXTRACTIONS setting
   - Review logs for errors
   - Restart the service

## Performance Tuning

### Concurrency Settings
```env
# Adjust based on system resources
MAX_CONCURRENT_EXTRACTIONS=5  # More concurrent jobs
EXTRACTION_TIMEOUT=60000       # Longer timeout for slow sites
```

### Resource Limits (Docker)
```yaml
# In docker-compose.extractor.yml
deploy:
  resources:
    limits:
      cpus: '4'      # More CPU
      memory: 8G     # More RAM
```

## Security Considerations

1. **Run in isolated environment**: Use Docker or VM
2. **Limit network access**: Configure firewall rules
3. **Secure Supabase keys**: Use environment variables
4. **Monitor extraction activity**: Check logs regularly
5. **Rate limiting**: Respect website terms of service

## Development

### Adding New Extractors

1. Create extractor class in `selenium_tax_extractors.py`
2. Register in `extractor_ui_service.py`:
   ```python
   self.extractors["new_county"] = NewCountyExtractor()
   ```
3. Add jurisdiction mapping in extraction logic

### Testing
```bash
# Test API endpoints
curl http://localhost:8001/api/status

# Test WebSocket
wscat -c ws://localhost:8001/ws
```

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review API docs at http://localhost:8001/docs
3. Verify Supabase connection and data
4. Check Docker container status if using Docker
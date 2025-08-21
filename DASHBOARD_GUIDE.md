# 🎯 Integrated Dashboard Guide

Complete guide for the Supabase-integrated Streamlit dashboard for tax extraction monitoring.

## 🚀 Quick Start

### 1. Ensure Services are Running

```bash
# API Service (if not already running)
python api_service_supabase.py

# Dashboard
streamlit run dashboard_supabase.py
```

### 2. Access the Dashboard

Open your browser to: **http://localhost:8502**

### 3. Login Options

#### Option A: Supabase Authentication
Use real credentials if you've created users:
- Email: `admin@taxextractor.com`
- Password: `Admin123!@#`

#### Option B: Demo Mode
Click "👁️ Demo Mode" to explore without authentication (limited features)

## 📊 Dashboard Features

### 1. **Overview Tab** 📊
Real-time metrics and KPIs:
- **Total Properties**: 102 properties in database
- **Total Entities**: 43 entities tracked
- **Amount Due**: $50,058.52 in outstanding taxes
- **Properties with Balance**: Properties with unpaid taxes
- **Recent Extractions**: Latest tax data extraction activities

### 2. **Properties Tab** 🏘️
Complete property management:
- **Searchable Table**: All 102 properties with details
- **Filters**: 
  - By State (TX, NC, PA, AZ, CO, IA)
  - By Jurisdiction (Montgomery, Harris, etc.)
  - By Entity (parent companies)
- **Actions**:
  - Select properties for extraction
  - Export to CSV
  - View tax bill links

### 3. **Jobs Tab** 🔄
Extraction job monitoring:
- **Active Jobs**: Real-time progress tracking
- **Job History**: Past extraction results
- **Create New Jobs**: Start extraction for selected properties
- **Status Indicators**:
  - 🟢 Success
  - 🔴 Failed
  - 🟡 Pending
  - 🔵 Processing

### 4. **Analytics Tab** 📈
Data visualization and insights:
- **Properties by State**: Bar chart distribution
- **Tax Amount by Jurisdiction**: Top jurisdictions by tax liability
- **Payment Status**: Pie chart (Paid vs Outstanding)
- **Extraction Success Rate**: Performance metrics

### 5. **Settings Tab** ⚙️
System configuration and status:
- **API Configuration**: Connection settings
- **Database Info**: Current statistics
- **System Status**: Health checks

## 🔐 Authentication Features

### User Roles
- **Admin**: Full access to all features
- **User**: Standard access (no admin functions)
- **Demo**: Read-only access with limited features

### Session Management
- Automatic token refresh
- Secure logout
- Session persistence

## 🎨 Dashboard Interface

### Visual Elements
- **Gradient Metric Cards**: Eye-catching KPI displays
- **Interactive Tables**: Sortable, filterable data grids
- **Real-time Charts**: Plotly-powered visualizations
- **Status Badges**: Color-coded indicators
- **Responsive Layout**: Works on desktop and tablet

### Navigation
- **Sidebar**: Filters and controls
- **Tabs**: Organized content sections
- **Breadcrumbs**: Easy navigation
- **Quick Actions**: One-click operations

## 📡 Real-time Data Integration

### Data Sources
1. **Supabase Database**: 
   - Direct queries to properties table
   - Entity relationships
   - Extraction history

2. **API Integration**:
   - Job status from API
   - Health checks
   - Authentication endpoints

### Auto-refresh
- Enable in sidebar for 30-second updates
- Manual refresh button
- Last refresh timestamp

## 🛠️ Advanced Features

### Batch Operations
1. Select multiple properties
2. Click "Extract Selected"
3. Monitor progress in Jobs tab

### Export Capabilities
- **CSV Export**: Download filtered data
- **Report Generation**: Analytics summaries
- **API Integration**: Direct data access

### Filtering System
Multi-level filtering:
1. State → Jurisdiction → Entity
2. Amount ranges
3. Date ranges
4. Status filters

## 📝 Common Workflows

### 1. Check Property Status
1. Go to Properties tab
2. Use filters to find properties
3. View amount due and previous taxes
4. Check tax bill links

### 2. Start Extraction Job
1. Select properties in Properties tab
2. Click "Extract Selected"
3. Monitor in Jobs tab
4. View results when complete

### 3. Analyze Tax Liabilities
1. Go to Analytics tab
2. Review charts and metrics
3. Export data for reporting
4. Share insights

### 4. Monitor System Health
1. Check Overview metrics
2. View Settings → System Status
3. Monitor API health
4. Check database connectivity

## 🔧 Troubleshooting

### Common Issues

#### Dashboard Won't Load
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# Restart if needed
streamlit run dashboard_supabase.py
```

#### No Data Showing
1. Check API is running: http://localhost:8000/health
2. Verify database connection in Settings tab
3. Check RLS policies are configured correctly

#### Authentication Fails
1. Verify Supabase Auth is enabled
2. Check credentials are correct
3. Try Demo Mode for testing

#### Slow Performance
1. Enable caching in Settings
2. Reduce data limits in filters
3. Check network connectivity

## 🎯 Best Practices

### For Administrators
1. **Regular Monitoring**: Check daily for failed extractions
2. **Batch Processing**: Group similar properties for efficiency
3. **Export Reports**: Weekly/monthly summaries for stakeholders
4. **System Maintenance**: Clear old jobs periodically

### For Users
1. **Use Filters**: Narrow down data before operations
2. **Check Status**: Verify job completion before new extractions
3. **Export Data**: Keep local backups of important data
4. **Report Issues**: Use Settings tab to check system status

## 📊 Current Data Summary

Your dashboard is monitoring:
- **102 Properties** across 6 states
- **43 Entities** (parent companies)
- **$50,058.52** in current tax liabilities
- **$434,291.55** in previous year taxes
- **10+ Jurisdictions** tracked

### Top Jurisdictions by Tax Amount:
1. Johnston County, NC: $16,969.08
2. Granville County, NC: $10,359.78
3. Bethlehem SD, PA: $8,567.88
4. Duplin County, NC: $7,817.07
5. Craven County, NC: $4,655.01

### Property Distribution:
- Texas: 67 properties
- North Carolina: 23 properties
- Colorado: 5 properties
- Pennsylvania: 3 properties
- Arizona: 2 properties
- Iowa: 1 property

## 🚀 Next Steps

1. **Explore the Dashboard**: http://localhost:8502
2. **Create Test Extractions**: Try extracting a few properties
3. **Customize Filters**: Set up your preferred views
4. **Export Reports**: Generate your first tax summary
5. **Schedule Extractions**: Plan regular update cycles

## 📚 Additional Resources

- [Streamlit Documentation](https://docs.streamlit.io)
- [Supabase Dashboard](https://supabase.com/dashboard/project/klscgjbachumeojhxyno)
- [API Documentation](http://localhost:8000/docs)
- [Plotly Charts Guide](https://plotly.com/python/)

## ✅ Success Indicators

Your integrated dashboard is working when you can:
- ✅ Login with Supabase credentials
- ✅ See 102 properties in the Properties tab
- ✅ View real-time metrics in Overview
- ✅ Create and monitor extraction jobs
- ✅ Export data to CSV
- ✅ See analytics charts with actual data

The dashboard is now fully integrated with your Supabase database and ready for production use!
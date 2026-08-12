# SendGrid Email Setup Guide

This guide explains how to configure SendGrid for email notifications in the Expense Tracker application.

## Why SendGrid?

The application uses SendGrid instead of Gmail SMTP because:
- **Render Compatibility**: SendGrid works reliably on Render and cloud platforms
- **No Port Restrictions**: Avoids port 587 blocking issues
- **Better Reliability**: Dedicated email service with better deliverability
- **Non-blocking**: Emails are sent asynchronously in a background worker thread

## Setup Instructions

### 1. Create SendGrid Account
- Go to https://sendgrid.com/
- Sign up for a free account
- Verify your email address

### 2. Get Your API Key
1. Log in to SendGrid Dashboard
2. Go to **Settings** → **API Keys**
3. Click **Create API Key**
4. Name it: `expense-tracker`
5. Select **Full Access** (or custom permissions: Mail Send)
6. Copy the API key

### 3. Configure Render Environment Variables

Add this environment variable to your Render deployment:

```
SENDGRID_API_KEY=SG.your_api_key_here
```

**Note**: Replace `SG.your_api_key_here` with your actual API key.

### 4. Optional: Configure Sender Email

By default, emails are sent from `noreply@expensetracker.com`. To use a custom sender email:

```
SMTP_FROM=your-email@yourdomain.com
```

(You may need to verify this email with SendGrid for deliverability)

## How It Works

### Email Flow
1. User adds shared expense or records settlement
2. API returns immediate response to user
3. Email is queued in background
4. Background worker thread sends emails asynchronously
5. User is not blocked waiting for email delivery

### Architecture
```
User Request
    ↓
Add Expense/Settlement (DB updated)
    ↓
Return Success to User (Immediate)
    ↓
Queue Email
    ↓
Background Worker Thread (Sends email asynchronously)
```

## Email Notifications

### Types of Emails Sent

#### 1. Shared Expense Notifications
- **When**: User adds a shared expense
- **Recipients**: All participants (if their email is registered)
- **Content**: Expense summary, individual shares, settlement instructions

#### 2. Settlement Notifications
- **When**: User records a settlement payment
- **Recipients**: The person settled with (if email is registered)
- **Content**: Settlement amount, date, and notes

## Monitoring

### View Email Logs
In your Render service dashboard:
1. Go to **Logs**
2. Look for `Email sent to` messages indicating successful sends
3. Look for `Email failed:` messages for delivery issues

### Check SendGrid Dashboard
1. Log in to SendGrid
2. Go to **Mail** → **Bounces** or **Deliveries**
3. Monitor delivery status

## Troubleshooting

### Issue: "Email failed: 401 Unauthorized"
- **Cause**: Invalid SENDGRID_API_KEY
- **Fix**: Double-check your API key in Render environment variables

### Issue: "Email skipped: SENDGRID_API_KEY is not configured"
- **Cause**: Environment variable not set
- **Fix**: Add `SENDGRID_API_KEY` to Render environment variables

### Issue: Emails not being sent
- **Check 1**: Is the email address registered in friends list?
- **Check 2**: Check Render logs for errors
- **Check 3**: Verify API key validity in SendGrid dashboard

## API Key Rotation

If you need to regenerate your API key:
1. Go to SendGrid **Settings** → **API Keys**
2. Delete the old key
3. Create a new one
4. Update `SENDGRID_API_KEY` in Render
5. Redeploy the application

## Cost

SendGrid offers:
- **Free Tier**: 100 emails/day (perfect for personal use)
- **Paid**: $14.95+/month with higher limits

For small personal projects, the free tier is sufficient.

## Security Best Practices

1. **Never commit API keys** to GitHub (they're already in .gitignore)
2. **Use environment variables** only (never hardcode)
3. **Rotate keys periodically** (especially if exposed)
4. **Monitor usage** in SendGrid dashboard
5. **Set API key permissions** to minimum needed (Mail Send only)

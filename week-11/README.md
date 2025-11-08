# Resume Builder Platform - Week 11 Progress Report

**Name:** Yash Tripathi  
**Team:** Product Engineering  
**Tech Stack:** Ruby on Rails, React, Redux, PostgreSQL, Redis, Mixpanel  
**Current Week:** 11

---

## Week 11 (November 1, 2025)

**Focus:** Compliance, Functionality, and Reliability Enhancements

### Work Completed This Week

**1. Career Policy Misconduct Integration**
- Added policy misconduct modals across user interaction flows
- Integrated backend APIs for dynamic policy fetching
- Implemented conditional rendering based on user behavior
- Added policy acknowledgment logging

**2. Recruiter Portal Flagging System**
- Comprehensive flagging system for job postings and users
- Custom modals and flagging rules
- Priority handling for severe violations
- Role-based access controls
- Visual indicators for flagged content

**3. Save Button Revamp for Job Cards**
- Reworked UI/UX for better user experience
- Improved event handlers and reduced API calls
- Enhanced feedback states (loading, saved, unsaved)
- Reduced latency and improved responsiveness

**4. Job Portal Blocker for Violators**
- Blocker mechanism to restrict access for violators
- Integrated with user management system
- Backend validation and error handling
- Prevents false positives

**5. Analytics Event Implementation**
- Mixpanel integration for event tracking
- Tracking for flagging actions, policy modals, save button interactions
- Validated event accuracy and data flow

**6. Testing, Review, and Deployment**
- Developer testing (DE testing) for all features
- Deployed to testing environment
- Product team review and feedback incorporation
- Documentation for deployment steps

### Technologies Used
- React 18.2.0
- Redux Toolkit 1.9.7
- Ruby on Rails 7.0.0
- PostgreSQL
- Redis
- Mixpanel
- REST APIs
- Postman
- GitHub Actions

### Key Results
- Enhanced compliance mechanisms
- Improved user experience
- Expanded analytics coverage
- Strengthened recruiter portal
- All features deployed to testing environment

---

### Quick Start

```bash
# Backend
cd week-8
bundle install
rails db:migrate
rails server

# Frontend
cd week-9
npm install
npm start
```

**Test Users:**
- Recruiter: `recruiter@example.com` / `password123`
- Admin: `admin@example.com` / `password123`

---


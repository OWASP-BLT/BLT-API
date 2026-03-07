# BLT-API Postman Collection

Comprehensive Postman collection for testing the BLT-API Cloudflare Worker with auto-generated test scripts for all endpoints.

## Contents

- **BLT-API.postman_collection.json** - Complete API collection with 39 endpoints grouped by resource
- **BLT-API-Environment.postman_environment.json** - Environment variables with sensible defaults

## Quick Start

### Prerequisites

- [Postman](https://www.postman.com/downloads/) (Desktop or Web)
- BLT-API service running (e.g., `wrangler dev --port 8787`)

### Import Instructions

#### Option 1: Postman Desktop/Web GUI

1. **Open Postman**
   - Launch Postman desktop app or go to https://web.postman.co

2. **Import Collection**
   - Click `Import` button (top-left area)
   - Choose `File` or drag-and-drop `BLT-API.postman_collection.json`
   - Confirm import

3. **Import Environment**
   - Click the Environment settings icon (gear icon, top-right)
   - Click `Import`
   - Select `BLT-API-Environment.postman_environment.json`
   - The environment will be available in the dropdown

4. **Select Environment**
   - Use the environment dropdown (top-right) to switch to `BLT-API Environment`
   - All variables like `{{baseUrl}}`, `{{token}}`, etc. will now resolve

5. **Update Variables (Optional)**
   - Edit the environment to change `baseUrl` if using a different worker URL
   - Set `token` after successful login from `/auth/signin`
   - Adjust ID variables (`userId`, `bugId`, etc.) as needed

#### Option 2: Postman CLI (newman)

```bash
# Install newman (Postman CLI)
npm install -g newman

# Run all tests against the collection
newman run ./tests/postman/BLT-API.postman_collection.json \
  --environment ./tests/postman/BLT-API-Environment.postman_environment.json

# Run with custom base URL
newman run ./tests/postman/BLT-API.postman_collection.json \
  --environment ./tests/postman/BLT-API-Environment.postman_environment.json \
  --env-var "baseUrl=https://api.blt.example.com"

# Generate HTML report
newman run ./tests/postman/BLT-API.postman_collection.json \
  --environment ./tests/postman/BLT-API-Environment.postman_environment.json \
  --reporters html,cli \
  --reporter-html-export report.html
```

## Environment Variables

Configure these variables in the `BLT-API Environment` before running tests:

| Variable | Default | Description |
|----------|---------|-------------|
| `baseUrl` | `http://localhost:8787` | API base URL (worker endpoint) |
| `token` | `` (empty) | JWT auth token from `/auth/signin` |
| `verifyToken` | `` (empty) | Email verification token (from signup email) |
| `testUsername` | `test_user_123` | Username for signup/signin testing (parameterized) |
| `testEmail` | `test.user.123@example.com` | Email for signup testing (parameterized) |
| `testPassword` | `TestPass123!` | Password for signup/signin testing (parameterized) |
| `bugId` | `1` | Bug ID for `/bugs/{id}` requests |
| `userId` | `1` | User ID for `/users/{id}` requests |
| `domainId` | `1` | Domain ID for `/domains/{id}` requests |
| `organizationId` | `1` | Organization ID for `/organizations/{id}` requests |
| `projectId` | `1` | Project ID for `/projects/{id}` requests |
| `huntId` | `1` | Hunt ID for `/hunts/{id}` requests |
| `contributorId` | `1` | Contributor ID for `/contributors/{id}` requests |
| `repoId` | `1` | Repository ID for `/repos/{id}` requests |

## Running Tests

### Full Test Suite

1. **Select the collection** from the left sidebar
2. **Click the `Run` button** (triangle icon)
3. **Ensure `BLT-API Environment` is selected**
4. **Click `Run BLT-API`** to execute all requests sequentially
5. View test results in the Collection Runner

### Running Specific Request Groups

Each folder contains related endpoints. You can run individual folders:

1. **Auth** - Signup, signin, email verification
2. **Bugs** - Bug listing, creation, search
3. **Users** - User profiles, followers, contribution history
4. **Domains** - Domain info and tags
5. **Organizations** - Org data and repos/projects
6. **Projects** - Project listings and contributors
7. **Hunts** - Active/previous/upcoming hunts
8. **Stats** - Platform statistics
9. **Leaderboard** - User rankings and org leaderboards
10. **Contributors** - Individual contributors
11. **Repositories** - Repository information

### Running Individual Requests

1. **Click any request** in the collection hierarchy
2. **Review the request** (method, URL, headers, body, tests)
3. **Click `Send`** to execute
4. **Check the response** and test results tabs

## Test Coverage

**Every request includes automated tests:**

✅ Status code validation aligned to endpoint behavior (200/201, and conditional 400 for missing verify token)  
✅ Response is valid JSON

Example test output:
```text
GET /health
✓ Status code is 200
✓ Response is valid JSON
```

**Note:** POST endpoints that create resources return `201 Created` (`/auth/signup`, `/bugs`), while `POST /auth/signin` returns `200 OK`. `GET /auth/verify-email` expects `200` when `verifyToken` is set and `400` when `verifyToken` is empty during default runs.

## Authentication Workflow

1. **Sign up (optional)**
   - `POST /auth/signup` with `{{testUsername}}`, `{{testEmail}}`, `{{testPassword}}`
   - Returns `201 Created` on success
   - Check email for verification link
   - Note the `user_id` from response
   - **Tip:** Change `testUsername`/`testEmail` variables to create unique test accounts

2. **Verify email**
   - `GET /auth/verify-email?token={{verifyToken}}`
   - Extract token from email verification link

3. **Sign in**
   - `POST /auth/signin` with `{{testUsername}}`, `{{testPassword}}`
   - Returns `200 OK` with JWT token
   - Copy the returned `token` value

4. **Set auth token**
   - Edit environment: set `token` to the value from step 3
   - Enable the `Authorization: Bearer {{token}}` header on protected endpoints
   - All requests will now use this token

## Common Workflows

### List All Bugs
1. `GET /bugs?page=1&per_page=20`
2. View response for bug IDs
3. Set environment variable `bugId` to a real ID
4. `GET /bugs/{{bugId}}` to view details

### Get User Profile
1. `GET /users?page=1&per_page=20`
2. Copy a user ID from the response
3. Set environment variable `userId`
4. `GET /users/{{userId}}/profile` for full profile with stats

### Create a Bug Report
1. First, gather a domain ID: `GET /domains?page=1&per_page=5`
2. Set environment variables `domainId` and `userId` to valid IDs
3. `POST /bugs` with required fields (`url`, `description`) and optional field `domain`
4. Response includes the newly created bug ID
5. Verify with `GET /bugs/{newId}`

### Search Bugs
1. `GET /bugs/search?q=sql%20injection&limit=10`
2. Adjust `q` parameter and `limit` as needed

## Troubleshooting

### `{{baseUrl}} is not defined`
- Ensure environment `BLT-API Environment` is selected (dropdown top-right)
- Verify the environment was imported correctly

### `401 Unauthorized` or `403 Forbidden`
- Set the `Authorization` header to Bearer token
- In Postman, enable the header checkbox if it's disabled
- Verify `token` variable is set and valid

### `404 Not Found` on parameterized routes
- Check that `{{userId}}`, `{{bugId}}`, etc. are set to valid IDs
- Use list endpoints first to get real IDs from the database

### `Connection refused` on localhost
- Ensure `wrangler dev` is running on port 8787
- Or update `baseUrl` environment variable to match your worker URL

### Signup fails with "User already exists"
- Change `testUsername` and `testEmail` environment variables to unique values
- The collection uses parameterized credentials for reusability

### Tests failing with wrong status code
- `POST /auth/signup` and `POST /bugs` return `201 Created`
- `POST /auth/signin` returns `200 OK`
- All GET endpoints return `200 OK`
- Tests are configured with the correct expected status codes

## Additional Resources

- [BLT-API Documentation](../../README.md)
- [Postman Learning Center](https://learning.postman.com/)
- [Newman CLI Documentation](https://learning.postman.com/docs/postman-cli/newman/newman-intro/)

## Notes

- **Auto-generated collection:** Includes all 39 routes from `src/main.py`
- **Request examples:** Payload samples are realistic based on handler parsing logic
- **No side effects:** Most requests are GET and safe to run repeatedly
- **Test scripts:** All requests validate status code and JSON structure

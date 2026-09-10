# Admin Dashboard (React)

Trivighna-operated admin panel for managing B2B client chatbots.

## Features

- Admin authentication (JWT)
- Create/manage B2B client companies
- Upload documents (max 5) and website URLs (max 3) per client
- Monitor training jobs with live polling
- Configure agent behavior (name, tone, instructions)
- Manage domain whitelist for widget embedding
- Copy embed script for client websites

## Run

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:5173

## Default Admin

After starting backend, click "Seed Default Admin" on login page:
- Email: `admin@trivighna.com`
- Password: `admin123`

## Environment

```bash
VITE_API_URL=http://localhost:8000/api
```

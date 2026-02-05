# Frontend Guide

## Technology Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Router v6** - Routing
- **React Query** - Server state management
- **Axios** - HTTP client
- **Lucide React** - Icons

## Project Structure

```
web/
├── src/
│   ├── api/                    # API client modules
│   │   ├── client.ts           # Axios instance with interceptors
│   │   ├── auth.ts             # Auth API calls
│   │   ├── profiles.ts         # Profile API calls
│   │   ├── jobs.ts             # Job API calls
│   │   ├── documents.ts        # Document API calls
│   │   └── admin.ts            # Admin API calls
│   ├── components/             # Reusable components
│   │   └── Layout.tsx          # Main layout with sidebar
│   ├── contexts/               # React contexts
│   │   └── AuthContext.tsx     # Authentication state
│   ├── pages/                  # Page components
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── ProfilesPage.tsx
│   │   ├── ProfileFormPage.tsx
│   │   ├── JobsPage.tsx
│   │   ├── JobDetailPage.tsx
│   │   ├── AddJobPage.tsx
│   │   ├── TopJobsPage.tsx
│   │   ├── DocumentsPage.tsx
│   │   └── admin/
│   │       ├── AdminDashboard.tsx
│   │       ├── AdminJobsPage.tsx
│   │       └── AdminScraperPage.tsx
│   ├── tests/                  # Test files
│   ├── types/                  # TypeScript types
│   │   └── index.ts            # All type definitions
│   ├── App.tsx                 # Main app with routes
│   ├── main.tsx                # Entry point
│   └── index.css               # Tailwind imports
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Authentication Flow

1. User enters credentials on login page
2. `AuthContext.login()` calls API and stores JWT in localStorage
3. `apiClient` interceptor adds token to all requests
4. Protected routes check `useAuth().user` before rendering
5. On 401 response, token is cleared and user redirected to login

## Key Components

### AuthContext

Provides authentication state and methods:

```tsx
const { user, isLoading, login, register, logout } = useAuth()
```

### Layout

Main layout with:
- Sidebar navigation
- User info section
- Logout button
- Content area (via `<Outlet />`)

### ProtectedRoute

Wrapper that redirects to login if not authenticated:

```tsx
<ProtectedRoute>
  <Component />
</ProtectedRoute>
```

### AdminRoute

Wrapper that redirects to home if not admin:

```tsx
<AdminRoute>
  <AdminComponent />
</AdminRoute>
```

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | User login form |
| Register | `/register` | User registration form |
| Dashboard | `/` | Overview with stats and quick actions |
| Profiles | `/profiles` | List and manage profiles |
| Profile Form | `/profiles/new`, `/profiles/:id` | Create/edit profile |
| Jobs | `/jobs` | Browse jobs with filters |
| Job Detail | `/jobs/:id` | View job and generate documents |
| Add Job | `/jobs/add` | Add job via URL, text, or manual entry |
| Top Jobs | `/jobs/top` | View top matched jobs |
| Documents | `/documents` | Document management (placeholder) |
| Admin Dashboard | `/admin` | System stats and quick actions |
| Admin Jobs | `/admin/jobs` | Manage all jobs |
| Admin Scraper | `/admin/scraper` | Run system operations |

## Styling

Tailwind CSS with custom components defined in `index.css`:

- `.btn` - Base button styles
- `.btn-primary` - Primary action button
- `.btn-secondary` - Secondary action button
- `.btn-danger` - Destructive action button
- `.input` - Form input styles
- `.label` - Form label styles
- `.card` - Card container

## Running

```bash
# Development
npm run dev

# Build
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Lint
npm run lint
```

## Environment

The frontend uses Vite's proxy to forward `/api` requests to the backend:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

For production, build the frontend and serve from FastAPI or deploy separately.

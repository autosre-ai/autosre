# AutoSRE V2 - Web UI

AI-powered SRE platform for automated incident investigation and response.

## Features

- 📊 **Dashboard** - System health overview, active alerts, and key metrics
- 🚨 **Alerts** - Real-time alert management with severity filtering
- 🔍 **Investigations** - AI-driven incident investigation with timeline view
- 💬 **Chat** - SRE chatbot for queries and assistance
- 📖 **Runbooks** - Library of operational procedures
- ⚙️ **Settings** - Integrations and preferences

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and bundling
- **TailwindCSS** for styling
- **React Router** for navigation
- **React Query** for data fetching
- **Recharts** for metrics visualization
- **Lucide Icons** for UI icons

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Environment Variables

Create a `.env` file:

```env
VITE_API_URL=/api
```

## Project Structure

```
src/
├── components/
│   ├── layout/       # Sidebar, Header, Layout
│   └── ui/           # Reusable UI components
├── context/          # React contexts (Theme)
├── data/             # Mock data for development
├── hooks/            # API hooks with React Query
├── lib/              # Utilities and API client
├── pages/            # Page components
│   ├── Dashboard.tsx
│   ├── Alerts.tsx
│   ├── AlertDetail.tsx
│   ├── Investigations.tsx
│   ├── InvestigationDetail.tsx
│   ├── Chat.tsx
│   ├── Runbooks.tsx
│   └── Settings.tsx
└── types/            # TypeScript types
```

## API Integration

The UI is designed to work with the AutoSRE V2 backend API. API hooks are located in `src/hooks/useApi.ts`.

### Endpoints Expected

- `GET /api/v1/alerts` - List alerts
- `GET /api/v1/alerts/:id` - Get alert details
- `POST /api/v1/alerts/:id/investigate` - Start investigation
- `GET /api/v1/investigations` - List investigations
- `GET /api/v1/investigations/:id` - Get investigation details
- `POST /api/v1/chat/sessions` - Create chat session
- `GET /api/v1/runbooks` - List runbooks
- `GET /api/v1/integrations` - List integrations

## Development

### Code Style

- TypeScript strict mode
- Functional components with hooks
- Tailwind for styling (no CSS files per component)

### Adding a New Page

1. Create component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/layout/Sidebar.tsx`

### Theme Support

The app supports light/dark mode via TailwindCSS `dark:` variants and the ThemeContext.

## Screenshots

### Dashboard
Overview of system health, active alerts, and metrics.

### Alerts
Filter and manage alerts by severity and status.

### Investigation
AI-powered investigation timeline with evidence and recommendations.

### Chat
Natural language interface for SRE operations.

## License

MIT

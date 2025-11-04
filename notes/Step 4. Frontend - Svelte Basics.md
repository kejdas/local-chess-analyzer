# Step 4. Frontend - Svelte Basics

## Overview

This step focuses on building the frontend user interface using Svelte 5 and establishing the foundation for the web application. We'll create a basic application structure with routing and implement the Settings page as our first functional component.

## Goals

1. **Initialize Svelte Project Structure**
   - Set up the basic Svelte application layout
   - Configure Vite for development (HMR - Hot Module Replacement)
   - Prepare the project for production builds

2. **Implement Routing**
   - Set up client-side routing using `svelte-routing` or `svelte-navigator`
   - Create navigation between different pages
   - Establish URL structure for the application

3. **Create Basic Application Layout**
   - Design the main `App.svelte` component
   - Implement navigation menu/header
   - Set up page container structure

4. **Build Settings Page**
   - Create `Settings.svelte` component
   - Fetch current settings from backend (`GET /api/settings`)
   - Display settings in an editable form
   - Save settings changes to backend (`PUT /api/settings`)
   - Provide user feedback on save success/failure

## Why This Approach?

### Foundation First
- Backend API is already functional and tested
- Settings are fundamental to the application
- Establishes patterns for future components

### Progressive Complexity
- Settings UI is simpler than game lists or chess visualization
- Good starting point to establish:
  - API communication patterns
  - State management
  - Form handling
  - Error handling

### Immediate Value
- Users can configure their Chess.com username
- Adjust Stockfish analysis parameters
- Makes the application immediately usable

### Technical Benefits
- Validates CORS configuration
- Tests frontend-backend integration
- Establishes component patterns
- Sets up routing structure for future pages

## Implementation Plan

### 1. Project Setup

**Frontend Structure:**
```
frontend/
├── src/
│   ├── App.svelte              # Main application component
│   ├── main.js                 # Entry point
│   ├── app.css                 # Global styles
│   ├── lib/
│   │   ├── components/
│   │   │   ├── Header.svelte   # Navigation header
│   │   │   ├── Settings.svelte # Settings page
│   │   │   └── Home.svelte     # Dashboard/home page
│   │   └── api/
│   │       └── client.js       # API client functions
│   └── assets/
├── vite.config.js
├── package.json
└── Dockerfile
```

### 2. Routing Setup

**Option 1: svelte-routing** (Recommended)
- Lightweight and simple
- Good for basic routing needs
- Easy to learn

```bash
npm install svelte-routing
```

**Option 2: svelte-navigator**
- Similar to React Router
- More features out of the box
- Good for complex routing

### 3. API Client

Create a centralized API client to handle all backend communication:

```javascript
// src/lib/api/client.js
const API_BASE_URL = 'http://localhost:42069';

export async function getSettings() {
  const response = await fetch(`${API_BASE_URL}/api/settings`);
  return response.json();
}

export async function updateSettings(settings) {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  });
  return response.json();
}
```

### 4. Settings Page Components

**Settings to Display:**
- Chess.com username (text input)
- Stockfish path (text input, read-only)
- Stockfish threads (number input)
- Stockfish hash size MB (number input)
- Analysis depth (number input)
- Analysis time MS (number input)
- Auto sync enabled (checkbox)
- Theme (select dropdown)

**User Experience:**
- Load current settings on page mount
- Show loading state while fetching
- Editable form fields
- Save button
- Success/error notifications
- Form validation

### 5. Basic Page Structure

```
┌─────────────────────────────────────────┐
│  Header / Navigation                    │
│  [Home] [Settings] [Sync] [Games]       │
├─────────────────────────────────────────┤
│                                         │
│  Page Content Area                      │
│  (Routed component renders here)        │
│                                         │
│                                         │
│                                         │
└─────────────────────────────────────────┘
```

## Expected Outcomes

After completing this step, users will be able to:

1. ✅ Navigate to the frontend at http://localhost:6969
2. ✅ See a clean, organized interface with navigation
3. ✅ Access the Settings page
4. ✅ View current settings loaded from the backend
5. ✅ Edit and save settings
6. ✅ Receive feedback on successful saves
7. ✅ Navigate between different pages (Home, Settings, etc.)

## Technical Validation

- [ ] Vite HMR working (changes reflect immediately)
- [ ] Routing functional (URL changes, back button works)
- [ ] API calls successful (check browser DevTools Network tab)
- [ ] CORS working (no console errors)
- [ ] Settings persist after save (refresh page to verify)
- [ ] Forms validate input appropriately
- [ ] Error handling displays user-friendly messages

## Next Steps After This

1. **Sync Control Page**
   - Button to trigger Chess.com sync
   - Display sync status
   - Show progress and results

2. **Games List Page**
   - Display imported games
   - Pagination controls
   - Basic filtering/sorting

3. **Game Detail Page**
   - Chess board visualization
   - PGN display
   - Game information

4. **Analysis Integration**
   - After Stockfish analysis is implemented
   - Display game analysis results
   - Highlight mistakes and best moves

## Technologies Used

- **Svelte 5**: Latest version with enhanced reactivity
- **Vite 7**: Fast build tool with HMR
- **svelte-routing**: Client-side routing
- **Fetch API**: For backend communication
- **CSS**: Styling (can be replaced with Tailwind, Bootstrap, etc.)

## Development Workflow

1. Make changes to Svelte components
2. Vite HMR automatically updates the browser
3. Test functionality in browser
4. Check browser console for errors
5. Verify API calls in Network tab
6. Rebuild Docker container when ready to deploy

## Notes

- Keep components small and focused
- Use Svelte's reactivity system effectively
- Handle loading and error states properly
- Provide clear user feedback
- Mobile responsiveness considerations for future
- Accessibility (a11y) best practices

## References

- [Svelte 5 Documentation](https://svelte.dev/docs)
- [Vite Documentation](https://vitejs.dev/)
- [svelte-routing GitHub](https://github.com/EmilTholin/svelte-routing)
- [Fetch API MDN](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)

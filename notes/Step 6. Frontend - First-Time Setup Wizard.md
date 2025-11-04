# Step 6: Frontend - First-Time Setup Wizard

## Overview

Create an intuitive first-time setup wizard that guides new users through initial configuration. The wizard will detect system resources, collect Chess.com username, and configure optimal Stockfish settings automatically.

## Goals

1. **Detect First-Time Users**
   - Check if `chess_com_username` is set
   - Show wizard only on first visit
   - Skip wizard if already configured

2. **System Resource Detection**
   - Fetch system capabilities via `GET /api/system-resources`
   - Display hardware information
   - Calculate recommended settings

3. **User-Friendly Configuration**
   - Multi-step wizard interface
   - Clear explanations for each setting
   - Smart defaults based on hardware
   - Allow customization

4. **Automatic Setup**
   - Apply recommended settings
   - Save configuration via `PUT /api/settings`
   - Redirect to dashboard after completion

## Implementation Plan

### 1. API Client Extension

Add to `frontend/src/lib/api/client.js`:
```javascript
export async function getSystemResources() {
  return apiFetch('/api/system-resources');
}
```

### 2. Setup Wizard Component

Create `frontend/src/lib/components/SetupWizard.svelte`:
- Modal overlay (full-screen)
- Multi-step interface
- Progress indicator
- Navigation buttons (Next, Back, Skip)

### 3. Wizard Steps

**Step 1: Welcome**
- Welcome message
- Brief explanation of app features
- "Get Started" button

**Step 2: Chess.com Username**
- Input for username
- Explanation of why it's needed
- Optional field note
- Validation feedback

**Step 3: System Resources**
- Display detected hardware:
  - CPU cores
  - RAM amount
  - Stockfish status
- Show recommended settings with explanations:
  - Threads: `cores / 2` (reserve for system)
  - Hash: `RAM * 0.15` (balanced performance)
- Allow manual adjustment
- Helpful tooltips

**Step 4: Confirmation**
- Summary of all settings
- Review before applying
- "Complete Setup" button
- Option to go back

### 4. App Integration

Update `frontend/src/App.svelte`:
```javascript
let showWizard = false;
let settingsLoaded = false;

onMount(async () => {
  const settings = await getSettings();
  if (!settings.chess_com_username) {
    showWizard = true;
  }
  settingsLoaded = true;
});
```

### 5. Wizard Logic Flow

```
Start
  ↓
Check Settings
  ↓
Username Set? → Yes → Skip Wizard → Show Dashboard
  ↓ No
Show Wizard
  ↓
Step 1: Welcome
  ↓
Step 2: Username Input
  ↓
Step 3: Resource Configuration
  ↓
Step 4: Confirmation
  ↓
Save Settings
  ↓
Close Wizard → Show Dashboard
```

## Recommended Settings Calculation

### Threads Calculation
```javascript
const recommendedThreads = Math.max(1, Math.floor(logicalCores / 2));
```
**Explanation:**
- Use half of available cores
- Leave other half for system/browser
- Minimum of 1 thread

**Examples:**
- 2 cores → 1 thread
- 4 cores → 2 threads
- 8 cores → 4 threads

### Hash Size Calculation
```javascript
const recommendedHashMb = Math.min(
  Math.max(128, Math.floor(availableRam * 0.15)),
  2048
);
```
**Explanation:**
- Use 15% of available RAM
- Minimum 128 MB
- Maximum 2048 MB
- Balanced between performance and system stability

**Examples:**
- 4 GB available → 614 MB
- 8 GB available → 1228 MB
- 16 GB available → 2048 MB (capped)

### Analysis Settings
```javascript
const recommendedDepth = 15; // Good balance
const recommendedTime = 1000; // 1 second per position
```

## UI/UX Design

### Wizard Container
- Full-screen modal overlay
- Semi-transparent backdrop
- Centered card (max-width: 600px)
- Clean, minimal design
- Progress indicator at top

### Visual Elements
- Icons for each step
- Color-coded sections
- Clear typography hierarchy
- Helpful tooltips/explanations
- Progress bar showing completion

### Responsive Design
- Works on mobile/tablet
- Touch-friendly buttons
- Scrollable content if needed
- Accessible keyboard navigation

## User Experience Features

**Clear Navigation:**
- "Next" button (primary action)
- "Back" button (secondary action)
- "Skip Setup" link (for advanced users)
- Step indicator (1/4, 2/4, etc.)

**Helpful Explanations:**
- Why each setting matters
- Impact of different values
- Recommended vs. custom settings
- Links to documentation

**Validation:**
- Real-time input validation
- Clear error messages
- Prevent invalid submissions
- Guide user to correct values

**Feedback:**
- Loading states during API calls
- Success confirmation
- Error handling with retry
- Progress indicators

## Technical Implementation

### State Management
```javascript
let wizardStep = 1;
let username = '';
let systemResources = null;
let customSettings = {
  threads: null,
  hashMb: null,
  depth: 15,
  timems: 1000
};
```

### API Calls
```javascript
// 1. Check if wizard needed
const settings = await getSettings();

// 2. Fetch system resources
const resources = await getSystemResources();

// 3. Save configuration
await updateSettings({
  chess_com_username: username,
  stockfish_threads: threads,
  stockfish_hash_mb: hashMb,
  analysis_depth: depth,
  analysis_time_ms: timems
});
```

### Error Handling
- Network errors: Show retry button
- Validation errors: Display inline
- System resource fetch fails: Use defaults
- Settings save fails: Allow retry or skip

## Testing Scenarios

**Test Cases:**
1. ✅ First visit with no username → Shows wizard
2. ✅ Already configured → Skips wizard
3. ✅ Complete all steps → Saves correctly
4. ✅ Skip wizard → Can access manually later
5. ✅ Invalid username → Shows validation
6. ✅ Network error → Allows retry
7. ✅ Back navigation → Preserves inputs
8. ✅ Close/refresh during wizard → Can restart

## Expected Outcomes

After completion:
- ✅ New users guided through setup
- ✅ Optimal settings configured automatically
- ✅ Chess.com username collected
- ✅ System resources detected and utilized
- ✅ Users understand their configuration
- ✅ Smooth onboarding experience
- ✅ Can skip and configure later
- ✅ Clear path to first game sync

## Future Enhancements

1. **Advanced Options:**
   - Show/hide advanced settings
   - Expert mode toggle
   - Custom analysis presets

2. **Help & Documentation:**
   - Inline help tooltips
   - Links to guides
   - Video tutorials
   - FAQ section

3. **Verification:**
   - Test Stockfish binary
   - Verify Chess.com username
   - Sample analysis run
   - Performance benchmark

4. **Onboarding Improvements:**
   - Interactive tour after setup
   - Sample game to analyze
   - Feature highlights
   - Tips and tricks

## Integration with Existing Features

**Settings Page:**
- Wizard can be re-run from settings
- "Run Setup Wizard Again" button
- Access to advanced configuration

**Dashboard:**
- Show setup completion status
- Quick access to wizard if incomplete
- Configuration health indicator

**Sync Page:**
- Prompt to configure username if missing
- Link back to wizard
- Inline username input option

## Accessibility

- Keyboard navigation (Tab, Enter, Escape)
- Screen reader friendly
- Clear focus indicators
- Proper ARIA labels
- Skip links for each step
- High contrast text

## Performance

- Lazy load wizard component
- Minimal bundle size impact
- Fast API calls (< 100ms total)
- Smooth animations
- No blocking operations

---

**Status:** 🚧 Ready to Implement
**Priority:** High
**Dependencies:** Step 4 (Frontend Basics), Step 5 (Resource Detection)
**Estimated Time:** 2-3 hours

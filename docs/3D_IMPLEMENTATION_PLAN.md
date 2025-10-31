# 3D Tumor Nanobot Simulation - Implementation Plan

## Overview
Transform the 2D Canvas-based tumor simulation into a stunning 3D WebGL visualization using Three.js and React Three Fiber. This will provide an immersive, interactive view of the tumor microenvironment with nanobots navigating in 3D space.

---

## Technology Stack

### Core Libraries
- **Three.js** (`three`) - Low-level 3D library
- **React Three Fiber** (`@react-three/fiber`) - React renderer for Three.js
- **React Three Drei** (`@react-three/drei`) - Useful helpers and abstractions
- **Orbit Controls** - Mouse/touch camera controls

### Why This Stack?
- **React Three Fiber**: React-friendly, declarative syntax, easier than vanilla Three.js
- **Three.js**: Industry standard, excellent performance, WebGL-accelerated
- **Drei**: Pre-built components (lights, controls, helpers) to speed up development
- **Desktop-only**: No mobile concerns, can use full WebGL features

---

## Implementation Phases

## Phase 0: Setup & Dependencies
**Goal**: Install libraries and create project structure  
**Time**: 30 minutes

### Step 0.1: Install Dependencies
```bash
cd frontend
npm install three @react-three/fiber @react-three/drei
npm install --save-dev @types/three
```

### Step 0.2: Update package.json
Verify dependencies are added correctly.

### Step 0.3: Create New Component Structure
```
frontend/src/components/
  └── tumor/
      ├── TumorSimulation3D.tsx          # Main 3D component
      ├── Scene3D.tsx                    # Three.js scene wrapper
      ├── TumorSphere.tsx                # 3D tumor model
      ├── Nanobot3D.tsx                   # Individual nanobot
      ├── TumorCell3D.tsx                 # Individual tumor cell
      ├── BloodVessel3D.tsx               # Blood vessel visualization
      ├── SubstrateField3D.tsx            # Substrate heatmap volume
      ├── CameraControls3D.tsx            # Camera controls
      └── helpers/
          ├── useTumorGeometry.ts        # Geometry calculations
          ├── useSubstrateTexture.ts     # Substrate texturing
          └── useNanobotAnimation.ts     # Nanobot movement
```

---

## Phase 1: Basic 3D Scene Setup
**Goal**: Create basic 3D scene with camera and lighting  
**Time**: 1-2 hours

### Step 1.1: Create Scene3D Component
**File**: `frontend/src/components/tumor/Scene3D.tsx`

**Features**:
- Initialize Three.js scene
- Setup PerspectiveCamera (75° FOV, appropriate aspect ratio)
- Add ambient and directional lighting
- Basic color scheme (light background, medical theme)

**Deliverables**:
```tsx
export function Scene3D({ children, ...props }) {
  return (
    <Canvas camera={{ position: [0, 0, 800], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <pointLight position={[-10, -10, -5]} intensity={0.3} />
      {children}
    </Canvas>
  );
}
```

### Step 1.2: Create CameraControls3D Component
**File**: `frontend/src/components/tumor/CameraControls3D.tsx`

**Features**:
- OrbitControls for mouse interaction
- Smooth damping for camera movement
- Reset camera button
- Zoom limits (min/max distance)
- Auto-rotate toggle (optional)

**Controls**:
- **Left click + drag**: Rotate around scene
- **Right click + drag**: Pan scene
- **Scroll**: Zoom in/out
- **Double click**: Reset camera

---

## Phase 2: 3D Tumor Sphere
**Goal**: Create the main 3D tumor model with zones  
**Time**: 2-3 hours

### Step 2.1: Create TumorSphere Component
**File**: `frontend/src/components/tumor/TumorSphere.tsx`

**Features**:
- **Base sphere**: Main tumor shape (radius from config)
- **Zone visualization**:
  - Necrotic core: Innermost sphere (25% radius, dark gray/black)
  - Hypoxic zone: Middle shell (25-70% radius, purple tint)
  - Viable tumor: Outer shell (70-100% radius, red tint)
- **Materials**:
  - Semi-transparent for depth visibility
  - Phong or StandardMaterial for realistic shading
  - Emissive glow for hypoxic zones
- **Boundary**: Clear edge marking tumor boundary

**Technical Details**:
```tsx
// Create layered spheres with different radii
const necroticRadius = tumorRadius * 0.25;
const hypoxicRadius = tumorRadius * 0.70;
const viableRadius = tumorRadius;

// Materials with transparency
const necroticMat = new MeshPhongMaterial({ 
  color: 0x333333, 
  transparent: true, 
  opacity: 0.8 
});
```

### Step 2.2: Add Zone Labels (in detailed mode)
- Text sprites or HTML overlays for zone labels
- Animated indicators showing zone boundaries

### Step 2.3: Add Tumor Boundary Visualization
- Wireframe sphere outline
- Pulsing effect for emphasis

---

## Phase 3: Blood Vessels
**Goal**: Render blood vessels as 3D tubes  
**Time**: 2-3 hours

### Step 3.1: Create BloodVessel3D Component
**File**: `frontend/src/components/tumor/BloodVessel3D.tsx`

**Features**:
- **3D tube geometry**: Cylinder/TubeGeometry for vessel structure
- **Pulsing animation**: Animated radius/mesh (sin wave)
- **Color scheme**: Green (oxygen + drug source)
- **Supply radius visualization**: Translucent spheres showing supply areas
- **Glow effects**: Enhanced visibility with emissive materials

**Technical Details**:
```tsx
// Vessel as 3D cylinder
const vesselGeometry = new THREE.CylinderGeometry(
  radius, radius, length, 16
);

// Supply radius as translucent sphere
const supplyGeometry = new THREE.SphereGeometry(
  supplyRadius, 32, 32
);
```

### Step 3.2: Animate Vessel Pulsing
- UseFrame hook for animation
- Sin wave for smooth pulsing
- Stagger pulsing for multiple vessels

---

## Phase 4: Tumor Cells
**Goal**: Render tumor cells as 3D particles/objects  
**Time**: 2-3 hours

### Step 4.1: Create TumorCell3D Component
**File**: `frontend/src/components/tumor/TumorCell3D.tsx`

**Approach Options**:
1. **Individual meshes** (for <1000 cells)
2. **Instanced rendering** (for >1000 cells) - Better performance
3. **Particle system** (for >5000 cells)

**Features**:
- **3D position**: Use full [x, y, z] from backend data
- **Color coding**:
  - Viable: Red
  - Hypoxic: Purple
  - Necrotic: Gray
  - Apoptotic: Yellow
- **Size variation**: Based on cell phase
- **Geometry**: Spheres or small icospheres

### Step 4.2: Optimize with Instanced Rendering
If cell count > 500, use `InstancedMesh` for performance:
```tsx
const cells = useMemo(() => {
  const instancedMesh = new THREE.InstancedMesh(
    geometry, material, cellCount
  );
  // Set positions using matrices
  return instancedMesh;
}, [tumorCells]);
```

### Step 4.3: Cell Lifecycle Visualization
- Fade out for dead cells
- Pulse effect for active cells
- Growth animation for dividing cells

---

## Phase 5: Nanobots
**Goal**: Create 3D nanobot models with movement trails  
**Time**: 3-4 hours

### Step 5.1: Create Nanobot3D Component
**File**: `frontend/src/components/tumor/Nanobot3D.tsx`

**Features**:
- **3D model**: Simple low-poly nanobot
  - Option 1: Octahedron (diamond shape)
  - Option 2: Custom geometry (rounded cube with corners)
  - Option 3: Sphere with directional indicator
- **State visualization**:
  - Color changes based on state (targeting, delivering, returning, etc.)
  - Glow effects matching 2D version
- **LLM indicator**: Gold ring or special material
- **Drug payload**: Inner glow intensity based on payload

### Step 5.2: Create Nanobot Trail System
**File**: `frontend/src/components/tumor/NanobotTrail.tsx`

**Features**:
- **Trail geometry**: Tube or line following nanobot path
- **Fade effect**: Trail fades over time
- **Color coding**: Based on substrate type or state
- **Smooth curves**: Use CatmullRomCurve3 for smooth paths

### Step 5.3: Animation System
**File**: `frontend/src/components/tumor/helpers/useNanobotAnimation.ts`

**Features**:
- **Smooth interpolation**: Between current and next position
- **Rotation towards direction**: Nanobot faces movement direction
- **State transitions**: Smooth color/material changes

---

## Phase 6: Substrate Fields (3D Heatmaps)
**Goal**: Visualize substrate data as 3D volume rendering  
**Time**: 4-5 hours (Most Complex)

### Step 6.1: Choose Visualization Method

**Option A: Volume Slices (Recommended)**
- Create multiple X/Y/Z plane slices
- Each slice shows substrate intensity as texture
- Can toggle slice visibility

**Option B: Isosurfaces**
- 3D surfaces showing equal substrate levels
- More complex but very visually striking

**Option C: Point Cloud**
- Dense particles colored by substrate value
- Good for overview, less detail

**Implementation**: Start with **Option A** (Volume Slices)

### Step 6.2: Create SubstrateField3D Component
**File**: `frontend/src/components/tumor/SubstrateField3D.tsx`

**Features**:
- **Texture generation**: Convert 2D substrate array to 3D texture
- **Shader material**: Custom shader for heatmap coloring
- **Color mapping**: Match existing substrate color schemes
- **Opacity control**: Adjustable transparency
- **Slice selector**: Toggle X/Y/Z slices

**Technical Details**:
```tsx
// Create data texture from substrate array
const texture = useMemo(() => {
  const data = new Float32Array(gridSize * gridSize);
  // Fill data from substrate values
  return new THREE.DataTexture(data, gridSize, gridSize);
}, [substrateData]);

// Shader for heatmap visualization
const material = new THREE.ShaderMaterial({
  uniforms: {
    substrateTexture: { value: texture },
    colorMap: { value: getColorMap(selectedSubstrate) }
  },
  vertexShader: `...`,
  fragmentShader: `...`
});
```

### Step 6.3: Implement Substrate Colors
Match existing 2D color schemes:
- Oxygen: Blue gradient
- Drug: Orange gradient
- IFN-γ: Purple
- TNF-α: Orange-red
- Perforin: Red
- Chemokine: Cyan

### Step 6.4: Add Substrate Controls
- Slice position slider
- Opacity control
- Toggle individual substrate types

---

## Phase 7: Integration & UI
**Goal**: Integrate 3D view with existing UI  
**Time**: 2-3 hours

### Step 7.1: Create TumorSimulation3D Component
**File**: `frontend/src/components/tumor/TumorSimulation3D.tsx`

**Features**:
- Main wrapper component
- Combines all 3D elements
- Handles props from parent (same as 2D version)
- Layout management

### Step 7.2: Add View Mode Toggle
**File**: `frontend/src/pages/TumorSimulation.tsx`

**Modifications**:
- Add "3D View" toggle button
- Conditionally render 2D or 3D component
- Preserve existing 2D functionality

```tsx
const [viewMode, setViewMode] = useState<'2D' | '3D'>('2D');

// In render:
{viewMode === '2D' ? (
  <TumorSimulationGrid {...props} />
) : (
  <TumorSimulation3D {...props} />
)}
```

### Step 7.3: Add 3D Controls UI
**File**: `frontend/src/components/tumor/ViewControls3D.tsx`

**Controls**:
- Reset camera button
- Auto-rotate toggle
- Show/hide elements (cells, vessels, substrates)
- Quality settings (High/Medium/Low)
- Export screenshot

### Step 7.4: Performance Optimization
- **Frustum culling**: Only render visible objects
- **LOD system**: Simpler models at distance
- **Object pooling**: Reuse geometries
- **Render throttling**: Limit FPS if needed

---

## Phase 8: Polish & Enhancements
**Goal**: Add visual polish and extra features  
**Time**: 3-4 hours

### Step 8.1: Enhanced Lighting
- Multiple light sources
- Dynamic shadows (optional, performance cost)
- Rim lighting for depth

### Step 8.2: Post-Processing Effects
- **Bloom**: Glow effects for vessels/nanobots
- **Tone mapping**: Better color rendering
- **Antialiasing**: Smoother edges

### Step 8.3: Annotations & Labels
- HTML overlays for zone labels
- Tooltips on hover
- Info panels

### Step 8.4: Cross-Section View
- Slice through tumor
- Adjustable slice position
- Multiple slice angles

### Step 8.5: Animation Settings
- Playback speed control
- Frame-by-frame stepping
- Time scrubbing

---

## Phase 9: Testing & Optimization
**Goal**: Ensure stability and performance  
**Time**: 2-3 hours

### Step 9.1: Performance Testing
- Test with various cell counts
- Measure FPS on different hardware
- Optimize for 60fps target

### Step 9.2: Browser Compatibility
- Chrome/Edge (Chromium)
- Firefox
- Safari

### Step 9.3: Error Handling
- WebGL context loss handling
- Fallback to 2D if WebGL unavailable
- Error boundaries

### Step 9.4: Memory Management
- Cleanup Three.js objects
- Dispose geometries/materials
- Prevent memory leaks

---

## Phase 10: Documentation & Final Polish
**Goal**: User experience polish  
**Time**: 1-2 hours

### Step 10.1: User Guide
- Keyboard shortcuts
- Mouse controls
- View tips

### Step 10.2: Loading States
- 3D scene loading indicator
- Progress for geometry generation

### Step 10.3: Settings Panel
- Visual quality options
- Substrate visibility toggles
- Camera presets

---

## Technical Specifications

### Performance Targets
- **60 FPS** on modern desktop (GTX 1060 or equivalent)
- **30 FPS minimum** on integrated graphics
- Support **1000+ cells** smoothly
- Support **50+ nanobots** with trails

### Browser Requirements
- WebGL 2.0 support
- Desktop browsers only (Chrome, Firefox, Edge, Safari)
- No mobile support needed

### Code Organization
```
components/tumor/
├── TumorSimulation3D.tsx      # Main entry point
├── Scene3D.tsx                # Scene setup
├── TumorSphere.tsx            # Tumor 3D model
├── Nanobot3D.tsx              # Nanobot mesh
├── TumorCell3D.tsx            # Cell visualization
├── BloodVessel3D.tsx          # Vessel tubes
├── SubstrateField3D.tsx       # Substrate volumes
├── CameraControls3D.tsx       # Camera interaction
├── ViewControls3D.tsx         # UI controls
└── helpers/
    ├── useTumorGeometry.ts
    ├── useSubstrateTexture.ts
    ├── useNanobotAnimation.ts
    └── usePerformance.ts
```

---

## Estimated Timeline

| Phase | Task | Time Estimate |
|-------|------|---------------|
| 0 | Setup & Dependencies | 30 min |
| 1 | Basic Scene Setup | 1-2 hours |
| 2 | 3D Tumor Sphere | 2-3 hours |
| 3 | Blood Vessels | 2-3 hours |
| 4 | Tumor Cells | 2-3 hours |
| 5 | Nanobots | 3-4 hours |
| 6 | Substrate Fields | 4-5 hours |
| 7 | Integration & UI | 2-3 hours |
| 8 | Polish & Enhancements | 3-4 hours |
| 9 | Testing & Optimization | 2-3 hours |
| 10 | Documentation | 1-2 hours |
| **Total** | | **22-32 hours** |

---

## Success Criteria

### Must Have (MVP)
- ✅ 3D tumor sphere with zone visualization
- ✅ Blood vessels as 3D tubes
- ✅ Nanobots visible and moving
- ✅ Camera controls (orbit, zoom, pan)
- ✅ Integration with existing UI
- ✅ Performance: 30+ FPS

### Should Have
- ✅ Tumor cells visualization
- ✅ Substrate field visualization
- ✅ Nanobot trails
- ✅ Detailed mode enhancements
- ✅ View mode toggle

### Nice to Have
- ✅ Cross-section view
- ✅ Post-processing effects
- ✅ Export functionality
- ✅ Advanced camera presets

---

## Next Steps

1. **Review this plan** - Make sure it aligns with your vision
2. **Start Phase 0** - Install dependencies
3. **Begin Phase 1** - Create basic scene
4. **Iterate** - Build incrementally, test as we go

Ready to start? Let's begin with Phase 0!

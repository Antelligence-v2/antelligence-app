# 3D Tumor Simulation Guide

## How to Use the Real 3D Simulation

The **main 3D simulation** is integrated into the **TumorSimulation** page (`/tumor`), not the test page.

### Steps to See the 3D Simulation:

1. **Go to the Tumor Simulation page**
   - Navigate to `/tumor` or click "Tumor Nanobot Simulation" from the home page

2. **Configure and Start a Simulation**
   - Set your parameters (number of nanobots, tumor size, etc.)
   - Click **"Start Simulation"** button
   - Wait for the simulation to complete

3. **Switch to 3D View**
   - Once simulation is running, click the **"🎮 3D View"** button
   - This will switch from 2D grid to 3D visualization

4. **Enable Detailed Mode for Full Effects**
   - Click **"🔬 Detailed Mode"** to see:
     - Nanobot movement trails
     - Enhanced visualizations
     - All substrate fields (oxygen, drug, pheromones)

5. **Control the Simulation**
   - Use **Play/Pause** to control animation
   - Use **Step Forward** to see individual frames
   - Switch between different substrate views (Oxygen, Drug, Trail, etc.)

### What You'll See in 3D:

- **Red Layered Sphere**: Tumor with necrotic core, hypoxic zone, and viable outer layer
- **Green Tubes**: Blood vessels with pulsing animations
- **Blue/Gold Diamonds**: Nanobots (blue = regular, gold = LLM-powered)
- **Colored Background**: Substrate fields (oxygen gradient, drug concentration, etc.)
- **Movement Trails**: Nanobot paths (only in detailed mode)

### Troubleshooting:

- **Blank Screen**: Make sure you've started a simulation first
- **No Movement**: Check that the simulation is playing (not paused)
- **No Trails**: Enable "Detailed Mode" to see movement trails
- **No Substrates**: Switch between different substrate types in the tabs

The 3D simulation uses **real simulation data** from your backend, so you'll see actual nanobot behavior, tumor growth, and substrate diffusion patterns.

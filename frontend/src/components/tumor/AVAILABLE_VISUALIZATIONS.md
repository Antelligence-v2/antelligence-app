# Available Visualizations from Simulation Data

## Data Available Per Step (from `step.metrics` and `step.nanobots`)

### Cell Phase Data (Real):
- `viable_cells` - Count of viable tumor cells
- `hypoxic_cells` - Count of hypoxic (low-oxygen) cells  
- `necrotic_cells` - Count of necrotic (dead) cells
- `apoptotic_cells` - Count of apoptotic (drug-killed) cells

### Nanobot Data (Real):
- `nanobots[]` array with:
  - `state`: 'searching', 'targeting', 'delivering', 'returning', 'reloading'
  - `is_llm_controlled`: boolean
  - `position`: (x, y, z)
  - `deliveries_made`: count per nanobot
  - `total_drug_delivered`: cumulative drug per nanobot

### Drug Delivery Data (Real):
- `total_deliveries` - Cumulative total deliveries
- `total_drug_delivered` - Cumulative drug delivered
- `deliveries_by_llm` - LLM-controlled nanobot deliveries
- `deliveries_by_rule` - Rule-based nanobot deliveries

### Substrate Data (Real, captured periodically):
- `substrate_data.oxygen` - 2D oxygen concentration map
- `substrate_data.drug` - 2D drug concentration map  
- `substrate_data.mean_values` - Average concentrations

### Cell Type Data (Real, from tumor_statistics):
- `cell_type_distribution.stem_cell`
- `cell_type_distribution.differentiated`
- `cell_type_distribution.resistant`
- `cell_type_distribution.invasive`

---

## Straightforward Visualizations We Can Create

### ✅ 1. Cell Phase Distribution Over Time
**Data**: `viable_cells`, `hypoxic_cells`, `necrotic_cells`, `apoptotic_cells`
**Chart Type**: Stacked Area Chart or Multi-line Line Chart
**What it shows**: How tumor composition changes (viable → hypoxic → necrotic/apoptotic)
**Why useful**: Shows treatment progression and tumor response

### ✅ 2. Nanobot State Distribution Over Time  
**Data**: Count nanobots by `state` from `step.nanobots[]`
**Chart Type**: Stacked Area Chart
**What it shows**: How many nanobots are searching vs targeting vs delivering
**Why useful**: Shows swarm coordination and efficiency

### ✅ 3. Cumulative Drug Delivery Progress
**Data**: `total_drug_delivered`, `total_deliveries`
**Chart Type**: Line Chart
**What it shows**: Total drug delivered and number of deliveries over time
**Why useful**: Shows treatment intensity and delivery rate

### ✅ 4. Cells Eliminated Over Time (Cumulative)
**Data**: `apoptotic_cells` (cumulative)
**Chart Type**: Area Chart or Line Chart
**What it shows**: Total cells killed as simulation progresses
**Why useful**: Direct measure of treatment effectiveness

### ✅ 5. Kill Rate Per Step (Incremental)
**Data**: `apoptotic_cells[i] - apoptotic_cells[i-1]`
**Chart Type**: Bar Chart or Area Chart
**What it shows**: Cells killed in each time step
**Why useful**: Shows treatment intensity at each moment

### ✅ 6. LLM vs Rule-Based Nanobot Performance
**Data**: `deliveries_by_llm`, `deliveries_by_rule`
**Chart Type**: Stacked Bar or Line Chart
**What it shows**: Comparison of AI-controlled vs rule-based nanobots
**Why useful**: Evaluates effectiveness of LLM decision-making

### ✅ 7. Active Nanobots Percentage
**Data**: Count of nanobots with state='targeting' or 'delivering' / total
**Chart Type**: Line Chart
**What it shows**: What percentage of swarm is actively treating
**Why useful**: Shows swarm efficiency and coordination

### ✅ 8. Substrate Concentration Maps (if available)
**Data**: `substrate_data.oxygen`, `substrate_data.drug` 
**Chart Type**: Heatmap or Contour Plot
**What it shows**: Spatial distribution of oxygen and drug
**Why useful**: Shows microenvironment and drug penetration patterns

### ✅ 9. Drug Efficiency Trend (if we fix it)
**Data**: `apoptotic_cells / total_drug_delivered` per step
**Chart Type**: Line Chart
**What it shows**: How efficiency changes over time
**Why useful**: Shows if treatment gets more/less efficient over time

### ✅ 10. Total Tumor Size Over Time
**Data**: Sum of all cell phases (viable + hypoxic + necrotic + apoptotic)
**Chart Type**: Line Chart
**What it shows**: Total tumor burden (accounting for growth + elimination)
**Why useful**: Shows net tumor progression

---

## Recommended Priority Order

1. **Cell Phase Distribution** - Most informative, shows tumor evolution
2. **Cumulative Cells Eliminated** - Simple, clear effectiveness metric
3. **Nanobot State Distribution** - Shows swarm behavior (already exists but can improve)
4. **Kill Rate Per Step** - Shows treatment intensity (already exists)
5. **Drug Delivery Progress** - Shows treatment delivery rate
6. **LLM vs Rule-Based** - If using mixed nanobots, shows AI advantage

---

## Which Ones Do We Already Have?

✅ Already implemented:
- Kill Rate Over Time (cells killed per step)
- Nanobot Swarm Coordination (active vs searching)
- Cell Type Targeting (but has issues)

⚠️ Need to fix:
- Treatment Effectiveness comparison (broken)
- Drug Efficiency (replaced with Drug Delivery Progress)

❌ Not yet created:
- Cell Phase Distribution Over Time
- LLM vs Rule-Based Performance
- Pure cumulative cells eliminated (without comparison)


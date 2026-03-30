 # TheSean

 A regression investigation harness for ML pipelines, latent action systems, and world models.

 TheSean runs paired A/B evaluations across ML/world model experiments, detects regressions, and provides an interactive investigation workbench for debugging episode-level divergences.

 ## What it does

 - Configure A/B experiment pairs with different weights, planners, or configs
 - Run paired evaluations with live telemetry
 - Detect regressions via bootstrap significance testing across 5 metrics
 - Drill into individual episodes with signal timelines and event detection

 ## Quickstart

 Python 3.10+ required.

 ### Install

```bash
pip install thesean
```

 ### Prerequisites: TheSean requires an ML repo with a compatible adapter.

 The only available adapter is for [f1worldmodel](https://github.com/justinsiek/f1worldmodel).

 Clone the repo and follow its README to install dependencies.

 ### Run

cd into the ML repo project root:

Example:
```bash
  cd f1worldmodel
  thesean
```

 This launches the TUI. From there:

 1. Select or create a case.
 2. Pick a track, configure Run A (baseline) and Run B (candidate) with different checkpoints or planner settings
 3. Run the evaluation
 4. View the verdict and drill into episodes to investigate divergences

 ## Available Adapters

 | Adapter | Repo | Status |
 |---------|------|--------|
 | `f1` | [justinsiek/f1worldmodel](https://github.com/justinsiek/f1worldmodel) | Beta |

 ## Status

 Beta. APIs may change.

 ## License

 MIT

Invoke the plotter agent to collect and present evidence during a Judicial Hearing or simulation validation run.

Usage: /plot-evidence <type> [args]

Evidence types:
  signal   <profile> [mode]     — signal diagnostic plot for one walker profile
  uart     <log_path>           — UART session output from a Renode log file
  sim      <profile> [mode]     — full simulation evidence: UART + signal plot combined

Arguments:
  profile:  flat | bad_wear | stairs | slope
  mode:     healthy (default) | pathological
  log_path: path to UART log file (e.g. simulator/logs/renode_flat.log)

Examples:
  /plot-evidence signal stairs
  /plot-evidence signal bad_wear pathological
  /plot-evidence uart simulator/logs/renode_flat.log
  /plot-evidence sim flat
  /plot-evidence sim slope pathological

Constitutional grounding:
  Amendment 11: signal plots mandatory after any walker_model or algorithm parameter change
  Bureaucracy Signal Plotting Standing Order: no Bill or hearing required

Now invoke the plotter agent with evidence type and arguments: "$ARGUMENTS"
Parse the first word as the evidence type. Pass remaining words as the target (profile or log_path).
If no type is given, print the usage above and stop.

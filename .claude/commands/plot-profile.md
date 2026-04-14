Invoke the plotter agent to generate a signal diagnostic plot for a single walker profile.

Usage: /plot-profile <profile> [mode]

Arguments:
- profile: flat | bad_wear | stairs | slope
- mode: healthy (default) | pathological

What this does:
1. Dispatches the plotter agent for the named profile only
2. Plotter reads walker_model.py, generates IMU signal, applies firmware-matched filters
3. Saves plot to docs/executive_branch_document/plots/<profile>_signal_check.png
4. Prints data table to stdout (peak values, zero-crossing timestamps, gap_ms)
5. If GAITSENSE_DEMO=1 is set, opens the plot in Preview automatically

Constitutional grounding:
- Amendment 11: mandatory after any walker_model.py or algorithm parameter change
- Bureaucracy Signal Plotting Standing Order: no Bill or hearing required

The plotter agent does NOT:
- Modify source code or algorithm parameters
- Interpret whether the signal is clinically correct (that is the Justice's role)
- Run simulations or build firmware
- Propose fixes based on what it observes

Example invocations:
  /plot-profile flat
  /plot-profile stairs
  /plot-profile bad_wear pathological

Now invoke the plotter agent with the profile "$ARGUMENTS".
Parse the first word as the profile name and the second word (if present) as the mode.
If no profile is given, print the usage above and stop — do not guess a profile.

The plotter agent must call:
    cd /Users/siyaoshao/gait_device && python simulator/walker_model.py --plot <profile> [--mode mode]

Do NOT write inline plot code. Use the established plot module in simulator/.

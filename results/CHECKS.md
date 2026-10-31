# Reproduction checks

- Original detector file preserved byte for byte; SHA-256 recorded in `sha256.json`.
- Executed the complete 700-image experiment and 30-sample desktop CPU benchmark.
- All seven detection counts match the original report results exactly.
- All four geometry values match the original report results.
- Generated example image matches the original image pixel for pixel.
- Verifier rejection checked using deliberately altered detection-count and geometry copies in memory; both were rejected. Committed experiment inputs and outputs were not changed by these checks.
- Original median CPU time: 339.768 ms. Reproduction median: 1096.517 ms. Both sets of genuine timing measurements are retained; timing is not an exact reproducibility requirement.

These checks were executed by an AI assistant on the available Windows AMD64 host. They are not independent human validation, real-camera measurements, or Jetson measurements. Execution metadata and hashes are recorded in `reproduction/verification.json`.

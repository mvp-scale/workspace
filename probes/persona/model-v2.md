# Model v2 (draft, 2026-10-04): five levels, state grid, decision matrix, one-layer cascade

Status: structure agreed in conversation; the facet list is OUR DRAFT and awaits the owner's confirmation. All numbers will be guesses until backtested. The matrix idea is cross-impact analysis (Gordon and Helmer 1966, Gordon and Hayward 1968) [checked]; the five levels, facets, markers and the one-layer rule are ours.

## Levels and their focus
| Level | Focus | Decisions |
|---|---|---|
| 0 World | leaders, blocs, global events | policy-like actions that become events for level 1 |
| 1 Country | government, institutions | same, become events for level 2 |
| 2 Region | local officials, local conditions | same, become events for level 3 |
| 3 Segment | demographic or industry group; how it experiences conditions | group markers; become inputs to level 4 |
| 4 Person | the individual's own states | buy, move, switch, travel, share... |

## State grid (per level, 10 x 10)
Rows: 10 state variables (levels 0 to 3 share the core variable ids; level 4 uses person states).
Columns (draft facets of each variable): 1 level (deviation from neutral), 2 trend, 3 acceleration, 4 duration, 5 breadth, 6 intensity, 7 certainty, 8 volatility, 9 salience, 10 carry-over.

## Decision matrix (per level)
10 decision types x the state grid. Output per decision: stage (calm, building, imminent) and direction (toward or away). Stage rule: thresholds on level, trend, duration, breadth and certainty. Reaction content is not predicted, only direction and timing window.

## Cascade rule
- Each event enters at the level it is about and applies once there (event id).
- A level affects ONLY the level directly below, through a 10 x 10 inheritance matrix (parent variables -> child variables), with a lag per hop.
- A level's decisions also affect only the level below, as new events.
- Four inheritance matrices (0>1, 1>2, 2>3, 3>4). The 3>4 matrix is the existing dial-to-element grid.

## Known gaps
Links between sibling nodes (allies, neighbours); no upward roll-up in v1; about 900 state-cell rules plus matrices to calibrate; facets are a guess; traceability requires every cell change to carry its event id and path.

## Added 2026-10-04: level-to-level distortion (the gap the owner named)
Information does not pass unchanged between levels. Each level has its own agenda, slant and noise. Every hop (parent level -> child level), for every state variable, is a CHANNEL with five numbers: gain (amplify or attenuate), lag, noise (seeded random draw), slant (the receiving level's bias, pushes the value up or down), gate (blocks signals below a threshold). Each node also carries an agenda vector (which variables it amplifies or suppresses), so two countries can pass the same world event on differently. Run many seeds to get ranges.
Precedents (found in search results, summaries only): social amplification of risk framework (Kasperson et al. 1988: signals are amplified or attenuated by 'amplification stations' such as scientists, news media, cultural groups and interpersonal networks); gatekeeping theory (Lewin 1947, White 1950: selection and omission); two-step flow (Katz and Lazarsfeld 1955: opinion leaders add their own interpretation); agenda setting and framing. Systems that could host it later: NDlib (Python diffusion and opinion-dynamics models on networks, including the independent cascade and threshold models; licence not found) and PySD (Python system dynamics: stocks, flows, delays, smoothing; licence not found).

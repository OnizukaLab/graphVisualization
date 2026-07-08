# graphVisualization

This project builds and visualizes social graphs from Wikipedia pages.

## Visualization

The graph visualizations use PageRank scores to determine node size and modularity-based clustering to determine node color.

## Structure

- `src/`
  - Shared scripts for crawling and building actor, politician, and tennis player graphs
- `data/actor/`
  - Output data and visualization artifacts for the actor graph
- `data/politician/`
  - Output data and visualization artifacts for the politician graph
- `data/tennisPlayer/`
  - Output data and visualization artifacts for the tennis player graph

## Outputs

Each dataset mainly produces the following files:

- `nodes.csv`
- `edges.csv`
- `manifest.json`

## Example: Tennis player graph visualization

![Tennis player graph](data/tennisPlayer/outputs/tennisPlayer.svg)

## PDFs

- [Actor graph PDF](data/actor/outputs/actor.pdf)
- [Politician graph PDF](data/politician/outputs/politician.pdf)
- [Tennis player graph PDF](data/tennisPlayer/outputs/tennisPlayer.pdf)

## Notes

- `data/**/cache/` contains local crawl cache files and is not tracked by Git.
- `data/**/outputs/` contains generated artifacts and is tracked in this repository.

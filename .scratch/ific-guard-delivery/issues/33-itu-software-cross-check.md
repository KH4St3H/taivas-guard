# 33 Cross-check pfd with ITU's software

Status: ready-for-human
Type: task
Size: M
Blocked by: none
Owns: `outputs/itu-cross-check.md`

## Why

Brief 02 names the ITU GIBC tool for pfd, and 06 A asks for "technically credible calculations". `ARCHITECTURE.md:152` plans to compare some 3074 networks with ITU's PFD GSO software, and README says it hasn't been done. The tools are Windows desktop software from https://www.itu.int/en/ITU-R/software/Pages/space-network-software.aspx, so a human runs them.

## Do

1. Run three to five 3074 GSO networks with pfd cases through ITU's software for the same mask.
2. Record ours against theirs in `outputs/itu-cross-check.md`, with any difference explained.

## Acceptance

- The file exists, and the README states the result instead of "not tested".

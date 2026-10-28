# BTP1 report

The report is written in parts on `docs/btp1-report`.

## Review in Overleaf

1. Open the [prescribed IEEE Conference template](https://www.overleaf.com/latex/templates/ieee-conference-template/grfzhhncsfqn).
2. Replace `main.tex` with the complete contents of [`btp1_report.tex`](btp1_report.tex).
3. Compile with pdfLaTeX.

The current draft is self-contained: title, placeholders for two authors,
abstract, a problem-led introduction, Cassini background, related work,
system model, shift policies, experimental setup, results and discussion,
conclusion, and cited references.
The background introduces repeating traffic, placement, shifts,
compatibility, and affinity graphs for readers who have not read the paper.
The three plots use PGFPlots with data included in the TeX source. It needs
no image uploads, separate section files, or bibliography file.

Related work connects the study to Cassini, Eclipse, and periodic offset
assignment. The system model defines traffic compatibility, shift waiting,
event progress, completion metrics, and the independent full-period check.
Its equations were checked against the simulator and traffic-checker code.
The policy section explains the decision rules and gives a numerical example.
The setup includes a workload table, paired comparisons, estimate scaling,
and the LCM scoring protocol. Settings were checked against saved manifests.

The complete draft builds locally to six pages, including references, within
the prescribed 6--8 page limit and double-column format. Check the page count
again after replacing the author placeholders in Overleaf.
The results cover policy gains, shift waits, estimate sensitivity,
and LCM score accuracy and calculation cost. Future work remains brief.
The IEEE class controls margins, fonts, and columns; these are not overridden.

Numerical claims were checked against the saved shift-policy and estimate-error
manifests on `research/shift-policies`, and the scoring diagnostic manifest on
`research/lcm-scoring`. Source commits are recorded in comments in the TeX file.
The report distinguishes completion-time estimates from offered-traffic checks.
The text presents the research questions, methods, and results in a project
narrative. Model and workload details define the experimental scope.

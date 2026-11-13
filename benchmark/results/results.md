# depscan benchmark results

Model per row in results.csv. Matching: name → evidence (±3 lines) → provider, with adjudication.

| set | repo | mode | labels | tool | TP | FP | FN | P | R | **F1** | strict F1 | name acc | versions | % LLM | LLM questions | cost $ (cold) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| heldout | full-stack-fastapi-template | static | 3 | 8 | 3 | 5 | 0 | 0.38 | 1.00 | 0.55 | 0.00 | 0.00 | 2/3 | 0.0 | 0 | 0.0 |
| heldout | shell_gpt | static | 2 | 4 | 1 | 3 | 1 | 0.25 | 0.50 | 0.33 | 0.00 | 0.00 | 0/0 | 0.0 | 0 | 0.0 |
| heldout | babyagi | static | 16 | 5 | 2 | 3 | 14 | 0.40 | 0.12 | 0.19 | 0.00 | 0.00 | 0/0 | 0.0 | 0 | 0.0 |
| heldout | **ALL heldout** | static | 21 | 17 | 6 | 11 | 15 | 0.35 | 0.29 | **0.32** | 0.00 | 0.00 | 2/3 | 0.0 | 0 | 0.0 |
| heldout | full-stack-fastapi-template | llm_only | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.67 | 0.67 | 1/3 | 100.0 | 382 | 6.1031 |
| heldout | shell_gpt | llm_only | 2 | 2 | 1 | 1 | 1 | 0.50 | 0.50 | 0.50 | 0.50 | 1.00 | 0/0 | 100.0 | 77 | 1.3082 |
| heldout | babyagi | llm_only | 16 | 8 | 8 | 0 | 8 | 1.00 | 0.50 | 0.67 | 0.42 | 0.62 | 1/1 | 100.0 | 310 | 5.1701 |
| heldout | **ALL heldout** | llm_only | 21 | 13 | 12 | 1 | 9 | 0.92 | 0.57 | **0.71** | 0.47 | 0.67 | 2/4 | 100.0 | 769 | 12.5814 |
| heldout | full-stack-fastapi-template | hybrid | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.67 | 0.67 | 2/3 | 80.9 | 27 | 0.555 |
| heldout | shell_gpt | hybrid | 2 | 2 | 1 | 1 | 1 | 0.50 | 0.50 | 0.50 | 0.50 | 1.00 | 0/0 | 92.2 | 61 | 1.064 |
| heldout | babyagi | hybrid | 16 | 7 | 7 | 0 | 9 | 1.00 | 0.44 | 0.61 | 0.35 | 0.57 | 1/1 | 75.5 | 157 | 2.7761 |
| heldout | **ALL heldout** | hybrid | 21 | 12 | 11 | 1 | 10 | 0.92 | 0.52 | **0.67** | 0.42 | 0.64 | 3/4 | 79.8 | 245 | 4.3951 |

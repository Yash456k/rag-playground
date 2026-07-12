# Training data review contract

`train.jsonl` contains 102 reviewed question-to-chunk examples covering every chunk
produced by the production ingestion function. The trainer resolves positive and
negative passages from the live corpus snapshot; passage text is not copied into the
dataset. `corpus-lock.json` pins both source files and the canonical 17-chunk snapshot,
so any corpus or chunking change stops training until the examples are reviewed again.

Each hard negative was manually compared with its positive and the exact locked chunk
text. A negative may discuss a nearby engineering theme, but it must not state the fact
needed to answer the paired question. In particular, adjacent overlap tails and the
RAG overview/case-study duplication were checked and supporting negatives were removed.

`dev.jsonl` is used only for pre/post retrieval metrics and release gates. Two earlier
locked sets were promoted here after exposing recruiter-style generalization failures;
they are no longer represented as unseen evidence. The current v3 holdout was written
after those promotions and remains isolated.
`locked_holdout.jsonl` is isolated from optimization, dev evaluation, and threshold
calibration. The validation command rejects exact normalized question duplication
between any of the three splits. The locked set is reserved for the separate final
interviewer-answer evaluation after artifacts are trained and integrated.

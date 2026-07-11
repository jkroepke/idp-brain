* 4.12: The first implementation pass is complete with the required tests green. It deliberately uses an injected trusted fetcher rather than a concrete SQL fetcher; the deep review will determine whether that still satisfies “retrieval returns
bundles” and will trace citation/hash/filter invariants, conflict handling, snapshot stability, and every public diagnostic field.

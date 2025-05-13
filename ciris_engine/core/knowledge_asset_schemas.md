# OriginTrail Knowledge Asset Schemas (Conceptual Content)

These describe the expected content structure within KAs stored on the DKG. The actual representation would be RDF triples (n-quads). JSON Schema or Ontologies (RDFS/OWL) could define this structure formally.

## A. Agent Profile KA:

-   `@id`: Agent UAL (Subject)
-   `rdf:type`: `ciris:AgentProfile`
-   `ciris:schemaVersion`: "1.0-beta"
-   `dcterms:created`: Timestamp
-   `dcterms:creator`: Creator UAL/DID
-   `did:verificationMethod`: \[Link to verification methods, e.g., public keys associated with the agent's DID]
-   `did:service`: \[Link to service endpoints for interacting with the agent]
-   `ciris:capability`: \[List of declared capabilities, potentially linking to Learned Model KAs]
-   `ciris:status`: "active" / "inactive" / "decommissioned"
-   `ciris:currentTask`: \[Optional list of UALs of currently assigned tasks]

## B. Task Definition KA:

-   `@id`: Task UAL (Subject)
-   `rdf:type`: `ciris:TaskDefinition`
-   `ciris:schemaVersion`: "1.0-beta"
-   `dcterms:created`: Timestamp
-   `dcterms:creator`: Originator UAL/DID
-   `dcterms:description`: Task description text
-   `ciris:taskStatus`: Current TaskStatus enum value (from foundational schemas)
-   `ciris:assignedAgent`: Agent UAL (if assigned)
-   `ciris:parametersSchema`: Optional UAL to schema KA for parameters
-   `ciris:parameters`: Structured parameters (e.g., embedded JSON-LD or link to data)
-   `ciris:priority`: Integer priority
-   `ciris:dependsOn`: \[List of UALs of prerequisite tasks]
-   `ciris:outcome`: \[Optional link to outcome data/KA]
-   `prov:wasGeneratedBy`: Link to the Thought ID or process that created this task KA state.

## C. Metathought Record KA:

-   `@id`: Metathought UAL (Subject)
-   `rdf:type`: `ciris:MetathoughtRecord`
-   `ciris:schemaVersion`: "1.0-beta"
-   `dcterms:created`: Timestamp
-   `prov:wasDerivedFrom`: UAL/ID of the triggering thought/observation/task
-   `ciris:metathoughtType`: e.g., "HeuristicRefinement", "PlanAdaptation", "SelfCorrection"
-   `ciris:reasoningTrace`: Text or link to detailed reasoning steps
-   `ciris:outcomeDescription`: Summary of the learning/adaptation
-   `ciris:learnedPattern`: Optional UAL to a new/updated Learned Model KA or heuristic description.

## D. Learned Model KA:

-   `@id`: Learned Model UAL (Subject)
-   `rdf:type`: `ciris:LearnedModel`
-   `ciris:schemaVersion`: "1.0-beta"
-   `dcterms:created`: Timestamp
-   `dcterms:creator`: Agent UAL
-   `ciris:modelType`: e.g., "NeuralNetwork", "DecisionTree", "HeuristicRuleSet"
-   `ciris:modelFormat`: e.g., "ONNX", "JSON", "PythonPickle" (Caution with pickle)
-   `ciris:modelDataLink`: Link to the actual model data (e.g., Iroh hash, IPFS CID, private storage URL)
-   `ciris:trainingDataRef`: Optional UAL to KA describing training data provenance
-   `ciris:performanceMetrics`: Structured metrics (accuracy, precision, etc.)
-   `ciris:validationProof`: Link to validation results/proof KA.

## E. Audit Log Batch KA:

-   `@id`: Audit Batch UAL (Subject)
-   `rdf:type`: `ciris:AuditLogBatch`
-   `ciris:schemaVersion`: "1.0-beta"
-   `dcterms:created`: Timestamp (end of batch period)
-   `prov:generatedAtTime`: Timestamp
-   `prov:wasGeneratedBy`: Node/Agent UAL responsible for batching
-   `ciris:startTime`: Start timestamp of the batch period
-   `ciris:endTime`: End timestamp of the batch period
-   `ciris:logEntryCount`: Number of entries in the batch
-   `ciris:merkleRoot`: Cryptographic hash (Merkle root) of the log entries in this batch.
-   `ciris:logDataLink`: Optional link to where the full batch data can be retrieved (if not embedded).

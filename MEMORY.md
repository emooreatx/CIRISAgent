# Channel-metadata approval cycle

Channel updates to the agent's graph memory are deferred on the first attempt. The DMA automatically spawns a new thought for the Wise Authority containing the original payload. When that follow-up thought arrives with `is_wa_correction` set and a `corrected_thought_id` referencing the deferred thought, the MemoryHandler applies the update without another deferral.

// Runs on the audio thread
class ChunkProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.sampleRate = options.processorOptions.sampleRate;
    this.chunkSize  = this.sampleRate * options.processorOptions.chunkSeconds;
    this.buffer = new Float32Array(this.chunkSize);
    this.filled = 0;
  }

  process(inputs) {
    const input = inputs[0][0]; // mono channel
    if (!input) return true;

    let offset = 0;
    while (offset < input.length) {
      const space = this.chunkSize - this.filled;
      const toCopy = Math.min(space, input.length - offset);
      this.buffer.set(input.subarray(offset, offset + toCopy), this.filled);
      this.filled += toCopy;
      offset += toCopy;

      if (this.filled === this.chunkSize) {
        // Send completed chunk to offscreen.js
        this.port.postMessage({ pcmBuffer: this.buffer.slice() });
        this.filled = 0; 
      }
    }
    return true;
  }
}

registerProcessor("chunk-processor", ChunkProcessor);
const SOUND_PROFILES = {
  "runner.jump": {
    notes: [
      { frequency: 740, duration: 0.04, type: "triangle", gain: 0.08 },
      { frequency: 920, duration: 0.05, type: "triangle", gain: 0.06, delay: 0.03 },
    ],
  },
  "runner.catch": {
    notes: [
      { frequency: 880, duration: 0.04, type: "triangle", gain: 0.1 },
      { frequency: 1180, duration: 0.06, type: "sine", gain: 0.08, delay: 0.025 },
    ],
  },
  "runner.hit": {
    notes: [
      { frequency: 220, duration: 0.08, type: "sawtooth", gain: 0.09 },
      { frequency: 160, duration: 0.12, type: "square", gain: 0.07, delay: 0.03 },
    ],
  },
  "runner.fall": {
    notes: [
      { frequency: 260, duration: 0.07, type: "square", gain: 0.08 },
      { frequency: 170, duration: 0.14, type: "sine", gain: 0.06, delay: 0.035 },
    ],
  },
  "runner.levelUp": {
    notes: [
      { frequency: 880, duration: 0.05, type: "triangle", gain: 0.08 },
      { frequency: 1100, duration: 0.06, type: "triangle", gain: 0.08, delay: 0.04 },
      { frequency: 1320, duration: 0.08, type: "sine", gain: 0.07, delay: 0.08 },
    ],
  },
  "runner.gameOver": {
    notes: [
      { frequency: 190, duration: 0.12, type: "sine", gain: 0.08 },
      { frequency: 140, duration: 0.2, type: "sine", gain: 0.06, delay: 0.06 },
    ],
  },
};

export function getSoundProfile(messageKey) {
  return SOUND_PROFILES[messageKey] ?? null;
}

export function createAudioController() {
  let audioContext = null;

  function getContext() {
    if (audioContext) {
      return audioContext;
    }

    const AudioCtor = globalThis.AudioContext ?? globalThis.webkitAudioContext;
    if (!AudioCtor) {
      return null;
    }

    audioContext = new AudioCtor();
    return audioContext;
  }

  return {
    play(messageKey) {
      const profile = getSoundProfile(messageKey);
      const context = getContext();

      if (!profile || !context) {
        return false;
      }

      const now = context.currentTime;
      const notes = profile.notes ?? [];

      for (const note of notes) {
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();
        const startAt = now + (note.delay ?? 0);
        const peakGain = note.gain ?? 0.08;

        oscillator.type = note.type;
        oscillator.frequency.setValueAtTime(note.frequency, startAt);
        gainNode.gain.setValueAtTime(0.0001, startAt);
        gainNode.gain.exponentialRampToValueAtTime(peakGain, startAt + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, startAt + note.duration);

        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        oscillator.start(startAt);
        oscillator.stop(startAt + note.duration);
      }

      return true;
    },
  };
}

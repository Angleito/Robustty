export interface CommandContext {
  command: string;
  songTitle?: string;
  queueLength?: number;
  error?: string;
  [key: string]: any;
}

export class KanyeResponseGenerator {
  private responses = {
    play: {
      success: [
        "Ok nigga, playing {song}",
        "You got it nigga, putting on {song}",
        "Aight nigga, {song} coming right up",
        "Say less nigga, playing {song} now",
        "Bet nigga, queuing up {song}"
      ],
      searching: [
        "Hold up nigga, looking for that",
        "Give me a sec nigga, searching for it",
        "Aight nigga, let me find that"
      ],
      notFound: [
        "Nah nigga, can't find that",
        "That ain't it nigga, try something else",
        "Can't locate that one nigga"
      ]
    },
    skip: {
      success: [
        "You got it nigga, skipping this track",
        "Aight nigga, next one coming up",
        "Say less nigga, moving to the next",
        "Ok nigga, skipping this joint"
      ],
      noTrack: [
        "Nothing to skip nigga",
        "Queue empty nigga, nothing playing",
        "Can't skip what ain't there nigga"
      ]
    },
    stop: {
      success: [
        "Aight nigga, stopping the music",
        "You got it nigga, shutting it down",
        "Ok nigga, music off",
        "Say less nigga, stopping playback"
      ]
    },
    queue: {
      withTracks: [
        "We got {count} tracks lined up nigga",
        "Queue sitting at {count} songs nigga",
        "Got {count} in the lineup nigga",
        "Check it nigga, {count} tracks waiting"
      ],
      empty: [
        "Queue empty nigga",
        "Nothing in the queue nigga",
        "No tracks lined up nigga"
      ]
    },
    pause: {
      success: [
        "Aight nigga, pausing it",
        "You got it nigga, music on pause",
        "Ok nigga, holding it right there"
      ]
    },
    resume: {
      success: [
        "Back at it nigga",
        "Music back on nigga",
        "Resuming playback nigga",
        "Let's go nigga, music back"
      ]
    },
    error: {
      general: [
        "Something went wrong nigga",
        "That ain't working right nigga",
        "Got an issue here nigga",
        "Can't do that right now nigga"
      ],
      voiceChannel: [
        "Get in a voice channel first nigga",
        "You ain't in voice nigga",
        "Join a channel first nigga"
      ]
    },
    greeting: [
      "What's good nigga",
      "Yeah nigga, what you need",
      "Speak on it nigga",
      "I'm listening nigga"
    ],
    unknown: [
      "What you saying nigga",
      "Say that again nigga",
      "I ain't catch that nigga",
      "Come again nigga"
    ]
  };

  generateResponse(context: CommandContext): string {
    const { command, songTitle, queueLength, error } = context;

    // Handle errors first
    if (error) {
      if (error.includes('voice channel')) {
        return this.getRandomResponse(this.responses.error.voiceChannel);
      }
      return this.getRandomResponse(this.responses.error.general);
    }

    // Handle specific commands
    switch (command) {
      case 'play':
        if (!songTitle) {
          return this.getRandomResponse(this.responses.play.searching);
        }
        return this.getRandomResponse(this.responses.play.success)
          .replace('{song}', songTitle);

      case 'skip':
        return this.getRandomResponse(this.responses.skip.success);

      case 'stop':
        return this.getRandomResponse(this.responses.stop.success);

      case 'queue':
        if (queueLength === 0) {
          return this.getRandomResponse(this.responses.queue.empty);
        }
        return this.getRandomResponse(this.responses.queue.withTracks)
          .replace('{count}', queueLength.toString());

      case 'pause':
        return this.getRandomResponse(this.responses.pause.success);

      case 'resume':
        return this.getRandomResponse(this.responses.resume.success);

      case 'greeting':
        return this.getRandomResponse(this.responses.greeting);

      default:
        return this.getRandomResponse(this.responses.unknown);
    }
  }

  generateErrorResponse(error: string): string {
    const context: CommandContext = { command: 'error', error };
    return this.generateResponse(context);
  }

  generateGreeting(): string {
    return this.getRandomResponse(this.responses.greeting);
  }

  private getRandomResponse(responses: string[]): string {
    return responses[Math.floor(Math.random() * responses.length)];
  }

  // For adding custom responses dynamically
  addCustomResponse(command: string, category: string, response: string): void {
    if (!this.responses[command]) {
      this.responses[command] = {};
    }
    if (!this.responses[command][category]) {
      this.responses[command][category] = [];
    }
    this.responses[command][category].push(response);
  }
}
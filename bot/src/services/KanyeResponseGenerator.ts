export interface CommandContext {
  command: string;
  songTitle?: string;
  queueLength?: number;
  error?: string;
  [key: string]: any;
}

export class KanyeResponseGenerator {
  private responses: Record<string, Record<string, string[]> | string[]> = {
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
    acknowledgment: [
      "Yeah nigga, I'm listening",
      "What you need nigga",
      "Talk to me nigga", 
      "I hear you nigga",
      "Go ahead nigga"
    ],
    unknown: [
      "What you saying nigga",
      "Say that again nigga",
      "I ain't catch that nigga",
      "Come again nigga"
    ],
    food: {
      watermelon: [
        "Man nigga, watermelon is straight fire",
        "Nothing beats fresh watermelon on a hot day nigga",
        "That watermelon juice hitting different nigga",
        "Watermelon the most refreshing fruit no cap nigga",
        "Summer ain't complete without watermelon nigga",
        "Watermelon got that sweet crispy goodness nigga",
        "Nothing like a cold slice of watermelon nigga",
        "Watermelon is nature's candy nigga"
      ],
      friedChicken: [
        "Yo nigga, fried chicken is the ultimate comfort food",
        "Crispy fried chicken with that perfect seasoning nigga",
        "Nothing beats that golden crispy chicken nigga",
        "Fried chicken is pure perfection nigga",
        "That fried chicken crunch is everything nigga",
        "Juicy chicken with that crispy coating nigga",
        "Fried chicken is straight soul food nigga",
        "Can't go wrong with some good fried chicken nigga"
      ],
      koolAid: [
        "Kool-Aid the drink of champions nigga",
        "That Kool-Aid hitting different with the right amount of sugar nigga",
        "Red Kool-Aid just hits different nigga",
        "Kool-Aid got that nostalgic flavor nigga",
        "Nothing like ice cold Kool-Aid on a hot day nigga",
        "Kool-Aid is that classic refresher nigga",
        "Mix that Kool-Aid just right and it's perfect nigga",
        "Kool-Aid brings back them childhood memories nigga"
      ],
      general: [
        "Food talk got me hungry now nigga",
        "We talking about the good stuff now nigga",
        "These flavors got me thinking nigga",
        "Food conversations are the best conversations nigga",
        "Nothing like talking about good eats nigga",
        "You know what's good when it comes to food nigga",
        "Food brings people together nigga",
        "We got taste when it comes to food nigga"
      ]
    }
  };

  generateResponse(context: CommandContext): string {
    const { command, songTitle, queueLength, error } = context;

    // Handle errors first
    if (error) {
      const errorResponses = this.responses.error as Record<string, string[]>;
      if (error.includes('voice channel')) {
        return this.getRandomResponse(errorResponses.voiceChannel);
      }
      return this.getRandomResponse(errorResponses.general);
    }

    // Handle specific commands
    switch (command) {
      case 'play':
        const playResponses = this.responses.play as Record<string, string[]>;
        if (!songTitle) {
          return this.getRandomResponse(playResponses.searching);
        }
        return this.getRandomResponse(playResponses.success)
          .replace('{song}', songTitle);

      case 'skip':
        const skipResponses = this.responses.skip as Record<string, string[]>;
        return this.getRandomResponse(skipResponses.success);

      case 'stop':
        const stopResponses = this.responses.stop as Record<string, string[]>;
        return this.getRandomResponse(stopResponses.success);

      case 'queue':
        const queueResponses = this.responses.queue as Record<string, string[]>;
        if (!queueLength || queueLength === 0) {
          return this.getRandomResponse(queueResponses.empty);
        }
        return this.getRandomResponse(queueResponses.withTracks)
          .replace('{count}', queueLength.toString());

      case 'pause':
        const pauseResponses = this.responses.pause as Record<string, string[]>;
        return this.getRandomResponse(pauseResponses.success);

      case 'resume':
        const resumeResponses = this.responses.resume as Record<string, string[]>;
        return this.getRandomResponse(resumeResponses.success);

      case 'greeting':
        return this.getRandomResponse(this.responses.greeting as string[]);

      case 'food':
        return this.generateRandomFoodTalk();

      default:
        return this.getRandomResponse(this.responses.unknown as string[]);
    }
  }

  generateErrorResponse(error: string): string {
    const context: CommandContext = { command: 'error', error };
    return this.generateResponse(context);
  }

  generateGreeting(): string {
    return this.getRandomResponse(this.responses.greeting as string[]);
  }

  generateAcknowledgment(): string {
    return this.getRandomResponse(this.responses.acknowledgment as string[]);
  }

  generateFoodResponse(foodType: 'watermelon' | 'friedChicken' | 'koolAid' | 'general'): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    return this.getRandomResponse(foodResponses[foodType]);
  }

  private getRandomResponse(responses: string[]): string {
    return responses[Math.floor(Math.random() * responses.length)];
  }

  // For adding custom responses dynamically
  addCustomResponse(command: string, category: string, response: string): void {
    if (!this.responses[command]) {
      this.responses[command] = {};
    }
    const commandResponses = this.responses[command] as Record<string, string[]>;
    if (!commandResponses[category]) {
      commandResponses[category] = [];
    }
    commandResponses[category].push(response);
  }

  // Food talk methods
  generateRandomFoodTalk(): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    const foodTypes = ['watermelon', 'friedChicken', 'koolAid', 'general'];
    const randomType = foodTypes[Math.floor(Math.random() * foodTypes.length)];
    return this.getRandomResponse(foodResponses[randomType]);
  }

  generateWatermelonTalk(): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    return this.getRandomResponse(foodResponses.watermelon);
  }

  generateFriedChickenTalk(): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    return this.getRandomResponse(foodResponses.friedChicken);
  }

  generateKoolAidTalk(): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    return this.getRandomResponse(foodResponses.koolAid);
  }

  generateGeneralFoodTalk(): string {
    const foodResponses = this.responses.food as Record<string, string[]>;
    return this.getRandomResponse(foodResponses.general);
  }
}
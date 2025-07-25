"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.KanyeResponseGenerator = void 0;
class KanyeResponseGenerator {
    responses = {
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
    generateResponse(context) {
        const { command, songTitle, queueLength, error } = context;
        if (error) {
            const errorResponses = this.responses.error;
            if (error.includes('voice channel')) {
                return this.getRandomResponse(errorResponses.voiceChannel);
            }
            return this.getRandomResponse(errorResponses.general);
        }
        switch (command) {
            case 'play':
                const playResponses = this.responses.play;
                if (!songTitle) {
                    return this.getRandomResponse(playResponses.searching);
                }
                return this.getRandomResponse(playResponses.success)
                    .replace('{song}', songTitle);
            case 'skip':
                const skipResponses = this.responses.skip;
                return this.getRandomResponse(skipResponses.success);
            case 'stop':
                const stopResponses = this.responses.stop;
                return this.getRandomResponse(stopResponses.success);
            case 'queue':
                const queueResponses = this.responses.queue;
                if (!queueLength || queueLength === 0) {
                    return this.getRandomResponse(queueResponses.empty);
                }
                return this.getRandomResponse(queueResponses.withTracks)
                    .replace('{count}', queueLength.toString());
            case 'pause':
                const pauseResponses = this.responses.pause;
                return this.getRandomResponse(pauseResponses.success);
            case 'resume':
                const resumeResponses = this.responses.resume;
                return this.getRandomResponse(resumeResponses.success);
            case 'greeting':
                return this.getRandomResponse(this.responses.greeting);
            default:
                return this.getRandomResponse(this.responses.unknown);
        }
    }
    generateErrorResponse(error) {
        const context = { command: 'error', error };
        return this.generateResponse(context);
    }
    generateGreeting() {
        return this.getRandomResponse(this.responses.greeting);
    }
    getRandomResponse(responses) {
        return responses[Math.floor(Math.random() * responses.length)];
    }
    addCustomResponse(command, category, response) {
        if (!this.responses[command]) {
            this.responses[command] = {};
        }
        const commandResponses = this.responses[command];
        if (!commandResponses[category]) {
            commandResponses[category] = [];
        }
        commandResponses[category].push(response);
    }
}
exports.KanyeResponseGenerator = KanyeResponseGenerator;
//# sourceMappingURL=KanyeResponseGenerator.js.map
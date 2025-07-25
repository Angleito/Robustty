declare const mockVoiceConnection: {
    state: {
        status: string;
        subscription: {
            player: {
                state: {
                    status: string;
                };
                play: jest.Mock<any, any, any>;
                on: jest.Mock<any, any, any>;
                off: jest.Mock<any, any, any>;
            };
        };
    };
    destroy: jest.Mock<any, any, any>;
};
declare const mockAudioStream: {
    pipe: jest.Mock<any, any, any>;
    on: jest.Mock<any, any, any>;
    destroy: jest.Mock<any, any, any>;
};
export { mockVoiceConnection, mockAudioStream };
//# sourceMappingURL=setup.d.ts.map
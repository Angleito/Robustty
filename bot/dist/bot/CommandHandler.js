"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CommandHandler = void 0;
const discord_js_1 = require("discord.js");
const AdminCommandHandler_1 = require("./AdminCommandHandler");
const logger_1 = require("../services/logger");
class CommandHandler {
    commands = [];
    bot;
    adminHandler;
    constructor(bot) {
        this.bot = bot;
        this.adminHandler = new AdminCommandHandler_1.AdminCommandHandler(bot);
        this.buildCommands();
    }
    buildCommands() {
        this.commands = [
            new discord_js_1.SlashCommandBuilder()
                .setName('play')
                .setDescription('Play a song')
                .addStringOption(option => option
                .setName('query')
                .setDescription('Song name or YouTube URL')
                .setRequired(true)),
            new discord_js_1.SlashCommandBuilder()
                .setName('skip')
                .setDescription('Skip the current song'),
            new discord_js_1.SlashCommandBuilder()
                .setName('stop')
                .setDescription('Stop playback and clear queue'),
            new discord_js_1.SlashCommandBuilder()
                .setName('queue')
                .setDescription('Show the current queue'),
            new discord_js_1.SlashCommandBuilder()
                .setName('nowplaying')
                .setDescription('Show the currently playing song'),
            ...this.adminHandler.getCommands()
        ];
    }
    async registerCommands() {
        const rest = new discord_js_1.REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
        try {
            logger_1.logger.info('Registering slash commands...');
            await rest.put(discord_js_1.Routes.applicationCommands(process.env.DISCORD_CLIENT_ID), { body: this.commands });
            logger_1.logger.info('Slash commands registered successfully');
        }
        catch (error) {
            logger_1.logger.error('Failed to register slash commands:', error);
        }
    }
    async handleCommand(interaction) {
        if (!interaction.isCommand())
            return;
        if (!interaction.isChatInputCommand())
            return;
        try {
            await interaction.deferReply();
            switch (interaction.commandName) {
                case 'play':
                    const query = interaction.options.getString('query', true);
                    await this.bot.play(query, interaction);
                    break;
                case 'skip':
                    if (!interaction.guildId) {
                        await interaction.editReply('This command can only be used in a server!');
                        break;
                    }
                    await this.bot.skip(interaction.guildId);
                    await interaction.editReply('Skipped current song');
                    break;
                case 'stop':
                    if (!interaction.guildId) {
                        await interaction.editReply('This command can only be used in a server!');
                        break;
                    }
                    await this.bot.stop(interaction.guildId);
                    await interaction.editReply('Stopped playback and cleared queue');
                    break;
                case 'queue':
                    await this.showQueue(interaction);
                    break;
                case 'nowplaying':
                    await this.showNowPlaying(interaction);
                    break;
                case 'admin':
                    await this.adminHandler.handleCommand(interaction);
                    break;
            }
        }
        catch (error) {
            logger_1.logger.error(`Command error (${interaction.commandName}):`, error);
            await interaction.editReply('An error occurred while executing the command');
        }
    }
    async showQueue(interaction) {
        const queue = this.bot.getQueueManager().getQueue();
        if (queue.length === 0) {
            await interaction.editReply('Queue is empty');
            return;
        }
        const itemsPerPage = 10;
        const totalPages = Math.ceil(queue.length / itemsPerPage);
        const currentPage = 1;
        const embed = {
            title: 'Music Queue',
            description: queue.slice(0, itemsPerPage).map((track, index) => `${index + 1}. **${track.title}** - Requested by <@${track.requestedBy}>`).join('\n'),
            footer: { text: `Page ${currentPage}/${totalPages} • Total: ${queue.length} songs` }
        };
        const controls = queue.length > itemsPerPage
            ? this.bot.getButtonHandler().createQueueControls(currentPage, totalPages)
            : null;
        await interaction.editReply({
            embeds: [embed],
            components: controls ? [controls] : []
        });
    }
    async showNowPlaying(interaction) {
        const current = this.bot.getQueueManager().getCurrent();
        if (!current) {
            await interaction.editReply('Nothing is playing');
            return;
        }
        const embed = {
            title: 'Now Playing',
            description: `**${current.title}**`,
            thumbnail: { url: current.thumbnail },
            fields: [
                { name: 'Duration', value: this.formatDuration(current.duration), inline: true },
                { name: 'Requested by', value: `<@${current.requestedBy}>`, inline: true }
            ]
        };
        const controls = this.bot.getButtonHandler().createPlayerControls();
        await interaction.editReply({
            embeds: [embed],
            components: [controls]
        });
    }
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}
exports.CommandHandler = CommandHandler;
//# sourceMappingURL=CommandHandler.js.map
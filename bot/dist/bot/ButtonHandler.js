"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ButtonHandler = void 0;
const discord_js_1 = require("discord.js");
const logger_1 = require("../services/logger");
class ButtonHandler {
    bot;
    constructor(bot) {
        this.bot = bot;
    }
    createPlayerControls() {
        return new discord_js_1.ActionRowBuilder()
            .addComponents(new discord_js_1.ButtonBuilder()
            .setCustomId('pause_resume')
            .setLabel('⏯️')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('skip')
            .setLabel('⏭️')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('stop')
            .setLabel('⏹️')
            .setStyle(discord_js_1.ButtonStyle.Danger), new discord_js_1.ButtonBuilder()
            .setCustomId('loop')
            .setLabel('🔁')
            .setStyle(discord_js_1.ButtonStyle.Secondary), new discord_js_1.ButtonBuilder()
            .setCustomId('shuffle')
            .setLabel('🔀')
            .setStyle(discord_js_1.ButtonStyle.Secondary));
    }
    createSelectionButtons() {
        return new discord_js_1.ActionRowBuilder()
            .addComponents(new discord_js_1.ButtonBuilder()
            .setCustomId('select_1')
            .setLabel('1')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('select_2')
            .setLabel('2')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('select_3')
            .setLabel('3')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('select_4')
            .setLabel('4')
            .setStyle(discord_js_1.ButtonStyle.Primary), new discord_js_1.ButtonBuilder()
            .setCustomId('select_5')
            .setLabel('5')
            .setStyle(discord_js_1.ButtonStyle.Primary));
    }
    createQueueControls(page, totalPages) {
        return new discord_js_1.ActionRowBuilder()
            .addComponents(new discord_js_1.ButtonBuilder()
            .setCustomId(`queue_first`)
            .setLabel('⏮️')
            .setStyle(discord_js_1.ButtonStyle.Secondary)
            .setDisabled(page === 1), new discord_js_1.ButtonBuilder()
            .setCustomId(`queue_prev_${page}`)
            .setLabel('◀️')
            .setStyle(discord_js_1.ButtonStyle.Secondary)
            .setDisabled(page === 1), new discord_js_1.ButtonBuilder()
            .setCustomId(`queue_page`)
            .setLabel(`${page}/${totalPages}`)
            .setStyle(discord_js_1.ButtonStyle.Secondary)
            .setDisabled(true), new discord_js_1.ButtonBuilder()
            .setCustomId(`queue_next_${page}`)
            .setLabel('▶️')
            .setStyle(discord_js_1.ButtonStyle.Secondary)
            .setDisabled(page === totalPages), new discord_js_1.ButtonBuilder()
            .setCustomId(`queue_last`)
            .setLabel('⏭️')
            .setStyle(discord_js_1.ButtonStyle.Secondary)
            .setDisabled(page === totalPages));
    }
    async handleButton(interaction) {
        if (!interaction.isButton())
            return;
        try {
            const customId = interaction.customId;
            if (customId.startsWith('search_')) {
                await this.handleSearchSelection(interaction);
                return;
            }
            await interaction.deferUpdate();
            switch (customId) {
                case 'pause_resume':
                    await this.handlePauseResume(interaction);
                    break;
                case 'skip':
                    if (!interaction.guildId) {
                        await interaction.editReply({ content: 'This button can only be used in a server!' });
                        break;
                    }
                    await this.bot.skip(interaction.guildId);
                    await interaction.editReply({ content: 'Skipped to next song! ⏭️' });
                    break;
                case 'stop':
                    if (!interaction.guildId) {
                        await interaction.editReply({ content: 'This button can only be used in a server!' });
                        break;
                    }
                    await this.bot.stop(interaction.guildId);
                    await interaction.editReply({
                        content: 'Stopped playback and cleared queue! ⏹️',
                        components: []
                    });
                    break;
                case 'loop':
                    await this.handleLoop(interaction);
                    break;
                case 'shuffle':
                    await this.handleShuffle(interaction);
                    break;
                default:
                    if (customId.startsWith('queue_')) {
                        await this.handleQueueNavigation(interaction, customId);
                    }
                    else if (customId.startsWith('select_')) {
                        await this.handleSimpleSelection(interaction, customId);
                    }
            }
        }
        catch (error) {
            logger_1.logger.error(`Button error (${interaction.customId}):`, error);
            try {
                if (interaction.deferred) {
                    await interaction.editReply({
                        content: 'An error occurred while processing the button click'
                    });
                }
                else {
                    await interaction.reply({
                        content: 'An error occurred while processing the button click',
                        ephemeral: true
                    });
                }
            }
            catch (responseError) {
                logger_1.logger.error('Failed to send error response:', responseError);
            }
        }
    }
    async handlePauseResume(interaction) {
        await interaction.editReply({ content: 'Pause/Resume functionality coming soon!' });
    }
    async handleLoop(interaction) {
        const queue = this.bot.getQueueManager();
        const currentLoop = queue.getLoopMode();
        let newLoop;
        let message;
        switch (currentLoop) {
            case 'none':
                newLoop = 'track';
                message = 'Now looping current track! 🔂';
                break;
            case 'track':
                newLoop = 'queue';
                message = 'Now looping entire queue! 🔁';
                break;
            case 'queue':
                newLoop = 'none';
                message = 'Loop disabled! ▶️';
                break;
        }
        queue.setLoop(newLoop);
        await interaction.editReply({ content: message });
    }
    async handleShuffle(interaction) {
        this.bot.getQueueManager().shuffle();
        await interaction.editReply({ content: 'Queue shuffled! 🔀' });
    }
    async handleQueueNavigation(interaction, customId) {
        const parts = customId.split('_');
        const action = parts[1];
        const currentPage = parts[2] ? parseInt(parts[2]) : 1;
        let newPage = currentPage;
        switch (action) {
            case 'first':
                newPage = 1;
                break;
            case 'prev':
                newPage = Math.max(1, currentPage - 1);
                break;
            case 'next':
                newPage = currentPage + 1;
                break;
            case 'last':
                break;
        }
        await this.updateQueueDisplay(interaction, newPage);
    }
    async updateQueueDisplay(interaction, page) {
        const queue = this.bot.getQueueManager().getQueue();
        const itemsPerPage = 10;
        const totalPages = Math.ceil(queue.length / itemsPerPage);
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const embed = {
            title: 'Music Queue',
            description: queue.slice(start, end).map((track, index) => `${start + index + 1}. **${track.title}** - <@${track.requestedBy}>`).join('\n') || 'Queue is empty',
            footer: { text: `Page ${page}/${totalPages} • Total: ${queue.length} songs` }
        };
        await interaction.editReply({
            embeds: [embed],
            components: [this.createQueueControls(page, totalPages)]
        });
    }
    async handleSimpleSelection(interaction, customId) {
        await interaction.editReply({
            content: 'Simple selection functionality not implemented. Please use the search command with proper search results.',
            components: []
        });
    }
    async handleSearchSelection(interaction) {
        try {
            const searchHandler = this.bot.getSearchResultHandler();
            const selectedVideo = await searchHandler.handleSearchSelection(interaction);
            if (!selectedVideo) {
                return;
            }
            if (!interaction.guildId) {
                await interaction.followUp({
                    content: 'This can only be used in a server!',
                    ephemeral: true
                });
                return;
            }
            const result = await this.bot.playSelectedVideoFromButton(selectedVideo, interaction.guildId, interaction.user.id);
            await interaction.followUp({
                content: result.message,
                ephemeral: !result.success
            });
        }
        catch (error) {
            logger_1.logger.error('Search selection error:', error);
            try {
                await interaction.followUp({
                    content: 'An error occurred while processing your selection',
                    ephemeral: true
                });
            }
            catch (followUpError) {
                logger_1.logger.error('Failed to send error response:', followUpError);
            }
        }
    }
}
exports.ButtonHandler = ButtonHandler;
//# sourceMappingURL=ButtonHandler.js.map
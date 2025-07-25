"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SearchResultHandler = void 0;
const discord_js_1 = require("discord.js");
const RedisClient_1 = require("./RedisClient");
const logger_1 = require("./logger");
class SearchResultHandler {
    redis;
    SESSION_TTL = 30;
    constructor() {
        this.redis = new RedisClient_1.RedisClient();
    }
    async createSearchSession(userId, guildId, query, results) {
        const sessionId = `search_${userId}_${Date.now()}`;
        const session = {
            sessionId,
            userId,
            guildId,
            query,
            results: results.slice(0, 5),
            createdAt: Date.now(),
            expiresAt: Date.now() + (this.SESSION_TTL * 1000)
        };
        await this.redis.set(`search:session:${sessionId}`, JSON.stringify(session), this.SESSION_TTL);
        logger_1.logger.info(`Created search session ${sessionId} for user ${userId}`);
        return sessionId;
    }
    async getSearchSession(sessionId) {
        const sessionData = await this.redis.get(`search:session:${sessionId}`);
        if (!sessionData) {
            return null;
        }
        try {
            return JSON.parse(sessionData);
        }
        catch (error) {
            logger_1.logger.error('Failed to parse search session:', error);
            return null;
        }
    }
    async deleteSearchSession(sessionId) {
        await this.redis.del(`search:session:${sessionId}`);
        logger_1.logger.info(`Deleted search session ${sessionId}`);
    }
    createSearchEmbed(query, results) {
        const embed = new discord_js_1.EmbedBuilder()
            .setTitle('🔍 Search Results')
            .setDescription(`Results for: **${query}**`)
            .setColor(0x3498db)
            .setTimestamp();
        results.forEach((video, index) => {
            const duration = this.formatDuration(video.duration);
            embed.addFields({
                name: `${index + 1}. ${video.title}`,
                value: `**Channel:** ${video.channel}\n**Duration:** ${duration}\n[Watch on YouTube](${video.url})`,
                inline: false
            });
        });
        embed.setFooter({
            text: 'Select a song using the buttons below • Session expires in 30s'
        });
        return embed;
    }
    createSelectionButtons(sessionId, resultCount) {
        const row = new discord_js_1.ActionRowBuilder();
        const buttonCount = Math.min(resultCount, 5);
        const numberEmojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'];
        for (let i = 0; i < buttonCount; i++) {
            row.addComponents(new discord_js_1.ButtonBuilder()
                .setCustomId(`search_select_${sessionId}_${i}`)
                .setLabel(`${i + 1}`)
                .setEmoji(numberEmojis[i])
                .setStyle(discord_js_1.ButtonStyle.Primary));
        }
        row.addComponents(new discord_js_1.ButtonBuilder()
            .setCustomId(`search_cancel_${sessionId}`)
            .setLabel('Cancel')
            .setEmoji('❌')
            .setStyle(discord_js_1.ButtonStyle.Secondary));
        return row;
    }
    async handleSearchSelection(interaction) {
        const customId = interaction.customId;
        if (!customId.startsWith('search_')) {
            return null;
        }
        const parts = customId.split('_');
        if (parts.length < 3) {
            return null;
        }
        const action = parts[1];
        const sessionId = parts[2];
        if (action === 'cancel') {
            await this.deleteSearchSession(sessionId);
            await interaction.update({
                content: '❌ Search cancelled.',
                embeds: [],
                components: []
            });
            return null;
        }
        if (action === 'select' && parts.length >= 4) {
            const selectedIndex = parseInt(parts[3]);
            const session = await this.getSearchSession(sessionId);
            if (!session) {
                await interaction.update({
                    content: '⏰ Search session expired. Please search again.',
                    embeds: [],
                    components: []
                });
                return null;
            }
            if (session.userId !== interaction.user.id) {
                await interaction.reply({
                    content: '❌ You can only select from your own search results.',
                    ephemeral: true
                });
                return null;
            }
            const selectedVideo = session.results[selectedIndex];
            if (!selectedVideo) {
                await interaction.update({
                    content: '❌ Invalid selection.',
                    embeds: [],
                    components: []
                });
                return null;
            }
            await this.deleteSearchSession(sessionId);
            await interaction.update({
                content: `✅ Selected: **${selectedVideo.title}**`,
                embeds: [],
                components: []
            });
            logger_1.logger.info(`User ${interaction.user.id} selected video ${selectedVideo.id} from search`);
            return selectedVideo;
        }
        return null;
    }
    async isSessionExpired(sessionId) {
        const exists = await this.redis.exists(`search:session:${sessionId}`);
        return !exists;
    }
    async cleanupExpiredSessions() {
        logger_1.logger.info('Cleaned up expired search sessions');
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
exports.SearchResultHandler = SearchResultHandler;
//# sourceMappingURL=SearchResultHandler.js.map
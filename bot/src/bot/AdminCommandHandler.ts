import { 
  SlashCommandBuilder, 
  CommandInteraction, 
  PermissionFlagsBits,
  EmbedBuilder 
} from 'discord.js';
import { MusicBot } from './MusicBot';
import { logger } from '../services/logger';

export class AdminCommandHandler {
  private bot: MusicBot;
  private adminRoleId?: string;

  constructor(bot: MusicBot) {
    this.bot = bot;
    this.adminRoleId = process.env.ADMIN_ROLE_ID;
  }

  getCommands() {
    return [
      new SlashCommandBuilder()
        .setName('admin')
        .setDescription('Admin commands')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
        .addSubcommand(subcommand =>
          subcommand
            .setName('auth')
            .setDescription('Open neko browser for authentication')
            .addStringOption(option =>
              option
                .setName('instance')
                .setDescription('Instance ID (e.g., neko-0)')
                .setRequired(true)
            )
        )
        .addSubcommand(subcommand =>
          subcommand
            .setName('status')
            .setDescription('Show health of all neko instances')
        )
        .addSubcommand(subcommand =>
          subcommand
            .setName('restart')
            .setDescription('Restart a specific neko instance')
            .addStringOption(option =>
              option
                .setName('instance')
                .setDescription('Instance ID (e.g., neko-0)')
                .setRequired(true)
            )
        )
        .addSubcommand(subcommand =>
          subcommand
            .setName('stats')
            .setDescription('Show playback statistics')
        )
        .addSubcommand(subcommand =>
          subcommand
            .setName('metrics')
            .setDescription('Show system metrics')
        )
        .addSubcommand(subcommand =>
          subcommand
            .setName('errors')
            .setDescription('Show recent errors')
        )
    ];
  }

  async handleCommand(interaction: CommandInteraction) {
    if (!this.isAdmin(interaction)) {
      await interaction.reply({ 
        content: 'You do not have permission to use admin commands.',
        ephemeral: true 
      });
      return;
    }

    if (!interaction.isChatInputCommand()) {
      return;
    }

    const subcommand = interaction.options.getSubcommand();

    try {
      await interaction.deferReply({ ephemeral: true });

      switch (subcommand) {
        case 'auth':
          await this.handleAuth(interaction);
          break;
        
        case 'status':
          await this.handleStatus(interaction);
          break;
        
        case 'restart':
          await this.handleRestart(interaction);
          break;
        
        case 'stats':
          await this.handleStats(interaction);
          break;
        
        case 'metrics':
          await this.handleMetrics(interaction);
          break;
        
        case 'errors':
          await this.handleErrors(interaction);
          break;
      }
    } catch (error) {
      logger.error(`Admin command error (${subcommand}):`, error);
      await interaction.editReply('An error occurred while executing the admin command');
    }
  }

  private isAdmin(interaction: CommandInteraction): boolean {
    if (!interaction.member || !interaction.guild) return false;
    
    const member = interaction.guild.members.cache.get(interaction.user.id);
    if (!member) return false;
    
    // Check if user has administrator permission
    if (member.permissions.has(PermissionFlagsBits.Administrator)) return true;
    
    // Check if user has the admin role
    if (this.adminRoleId && member.roles.cache.has(this.adminRoleId)) return true;
    
    return false;
  }

  private async handleAuth(interaction: CommandInteraction) {
    if (!interaction.isChatInputCommand()) {
      return;
    }
    const instanceId = interaction.options.getString('instance', true);
    
    const embed = new EmbedBuilder()
      .setTitle('🔐 Neko Authentication')
      .setDescription(`Opening browser for instance: ${instanceId}`)
      .addFields(
        { 
          name: 'Instructions', 
          value: '1. Log into YouTube in the browser\n2. Make sure "Remember me" is checked\n3. The session will be saved automatically' 
        },
        {
          name: 'Browser URL',
          value: `${process.env.NEKO_INTERNAL_URL}?instance=${instanceId}`
        }
      )
      .setColor(0x00FF00);

    await interaction.editReply({ embeds: [embed] });
  }

  private async handleStatus(interaction: CommandInteraction) {
    const nekoPool = this.bot.getNekoPool();
    const instances = await nekoPool.getAllInstances();
    
    const embed = new EmbedBuilder()
      .setTitle('🖥️ Neko Instance Status')
      .setColor(0x0099FF);

    for (const instance of instances) {
      const status = instance.isAuthenticated ? '✅ Authenticated' : '❌ Not Authenticated';
      const video = instance.currentVideo ? `Playing: ${instance.currentVideo}` : 'Idle';
      
      embed.addFields({
        name: instance.id,
        value: `${status}\n${video}`,
        inline: true
      });
    }

    await interaction.editReply({ embeds: [embed] });
  }

  private async handleRestart(interaction: CommandInteraction) {
    if (!interaction.isChatInputCommand()) {
      return;
    }
    const instanceId = interaction.options.getString('instance', true);
    const nekoPool = this.bot.getNekoPool();
    
    try {
      const instance = await nekoPool.getInstanceById(instanceId);
      if (!instance) {
        await interaction.editReply(`Instance ${instanceId} not found`);
        return;
      }

      await instance.restart();
      await interaction.editReply(`✅ Instance ${instanceId} restarted successfully`);
    } catch (error) {
      await interaction.editReply(`❌ Failed to restart instance ${instanceId}`);
    }
  }

  private async handleStats(interaction: CommandInteraction) {
    const stats = await this.bot.getPlaybackStrategy().getStats();
    
    const embed = new EmbedBuilder()
      .setTitle('📊 Playback Statistics')
      .setColor(0x00FF00)
      .addFields(
        { name: 'Direct Streams', value: stats.direct.toString(), inline: true },
        { name: 'Neko Fallbacks', value: stats.neko.toString(), inline: true },
        { name: 'Recent Failures', value: stats.recentFailures.toString(), inline: true }
      )
      .setTimestamp();

    await interaction.editReply({ embeds: [embed] });
  }

  private async handleMetrics(interaction: CommandInteraction) {
    const monitoring = this.bot.getMonitoringService();
    const metrics = await monitoring.getMetrics();
    
    if (!metrics) {
      await interaction.editReply('No metrics available');
      return;
    }

    const memoryMB = (metrics.system.memoryUsage.heapUsed / 1024 / 1024).toFixed(2);
    const uptimeHours = (metrics.system.uptime / 3600).toFixed(2);
    
    const embed = new EmbedBuilder()
      .setTitle('📈 System Metrics')
      .setColor(0x0099FF)
      .addFields(
        { name: 'Discord Ping', value: `${metrics.discord.ping}ms`, inline: true },
        { name: 'Guilds', value: metrics.discord.guilds.toString(), inline: true },
        { name: 'Voice Connections', value: metrics.discord.voiceConnections.toString(), inline: true },
        { name: 'Memory Usage', value: `${memoryMB}MB`, inline: true },
        { name: 'Uptime', value: `${uptimeHours} hours`, inline: true }
      )
      .setTimestamp();

    await interaction.editReply({ embeds: [embed] });
  }

  private async handleErrors(interaction: CommandInteraction) {
    const errorHandler = this.bot.getErrorHandler();
    const errorMetrics = await errorHandler.getErrorMetrics();
    
    const embed = new EmbedBuilder()
      .setTitle('⚠️ Error Metrics')
      .setColor(0xFF0000)
      .setDescription('Error counts by type:');

    for (const [type, count] of Object.entries(errorMetrics)) {
      if (count > 0) {
        embed.addFields({ 
          name: type.replace('_', ' ').toUpperCase(), 
          value: count.toString(), 
          inline: true 
        });
      }
    }

    await interaction.editReply({ embeds: [embed] });
  }
}
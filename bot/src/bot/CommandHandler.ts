import { REST, Routes, SlashCommandBuilder } from 'discord.js';
import { CommandInteraction } from 'discord.js';
import { MusicBot } from './MusicBot';
import { AdminCommandHandler } from './AdminCommandHandler';
import { logger } from '../services/logger';

export class CommandHandler {
  private commands: any[] = [];
  private bot: MusicBot;
  private adminHandler: AdminCommandHandler;

  constructor(bot: MusicBot) {
    this.bot = bot;
    this.adminHandler = new AdminCommandHandler(bot);
    this.buildCommands();
  }

  private buildCommands() {
    const baseCommands = [
      new SlashCommandBuilder()
        .setName('play')
        .setDescription('Play a song')
        .addStringOption(option =>
          option
            .setName('query')
            .setDescription('Song name or YouTube URL')
            .setRequired(true)
        ),
      
      new SlashCommandBuilder()
        .setName('skip')
        .setDescription('Skip the current song'),
      
      new SlashCommandBuilder()
        .setName('stop')
        .setDescription('Stop playback and clear queue'),
      
      new SlashCommandBuilder()
        .setName('queue')
        .setDescription('Show the current queue'),
      
      new SlashCommandBuilder()
        .setName('nowplaying')
        .setDescription('Show the currently playing song')
    ];

    // Only add voice commands if voice feature is enabled
    if (this.bot.isVoiceCommandsEnabled()) {
      baseCommands.push(
        new SlashCommandBuilder()
          .setName('voice')
          .setDescription('Enable voice commands in this voice channel'),
        
        new SlashCommandBuilder()
          .setName('novoice')
          .setDescription('Disable voice commands in this server')
      );
    }

    this.commands = [
      ...baseCommands,
      ...this.adminHandler.getCommands()
    ];
  }

  async registerCommands() {
    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN!);
    
    try {
      logger.info('Registering slash commands...');
      
      await rest.put(
        Routes.applicationCommands(process.env.DISCORD_CLIENT_ID!),
        { body: this.commands }
      );
      
      logger.info('Slash commands registered successfully');
    } catch (error) {
      logger.error('Failed to register slash commands:', error);
    }
  }

  async handleCommand(interaction: CommandInteraction) {
    if (!interaction.isCommand()) return;
    if (!interaction.isChatInputCommand()) return;

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
          
        case 'voice':
          await this.handleVoiceCommand(interaction);
          break;
          
        case 'novoice':
          await this.handleNoVoiceCommand(interaction);
          break;
          
        case 'admin':
          await this.adminHandler.handleCommand(interaction);
          break;
      }
    } catch (error) {
      logger.error(`Command error (${interaction.commandName}):`, error);
      await interaction.editReply('An error occurred while executing the command');
    }
  }

  private async showQueue(interaction: CommandInteraction) {
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
      description: queue.slice(0, itemsPerPage).map((track, index) => 
        `${index + 1}. **${track.title}** - Requested by <@${track.requestedBy}>`
      ).join('\n'),
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

  private async showNowPlaying(interaction: CommandInteraction) {
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

  private async handleVoiceCommand(interaction: CommandInteraction): Promise<void> {
    if (!this.bot.isVoiceCommandsEnabled()) {
      await interaction.editReply('Voice commands are not enabled on this bot. Contact the bot administrator to enable this feature.');
      return;
    }

    if (!interaction.guild) {
      await interaction.editReply('This command can only be used in a server!');
      return;
    }

    const member = interaction.guild.members.cache.get(interaction.user.id);
    if (!member?.voice.channel) {
      await interaction.editReply('You need to be in a voice channel to enable voice commands!');
      return;
    }

    try {
      await this.bot.enableVoiceCommands(member.voice.channel as any);
      
      const embed = {
        title: '🎤 Voice Commands Enabled',
        color: 0x00ff00,
        description: `Voice commands are now active in **${member.voice.channel.name}**!\n\nSay **"Kanye"** followed by your command:`,
        fields: [
          {
            name: 'Available Commands',
            value: '• **"Kanye play [song name]"** - Play a song\n• **"Kanye skip"** - Skip current song\n• **"Kanye stop"** - Stop playback\n• **"Kanye queue"** - Show queue info',
            inline: false
          },
          {
            name: 'Tips',
            value: '• Speak clearly and wait for the wake word detection\n• Voice commands work best in quiet environments\n• Use `/novoice` to disable voice commands',
            inline: false
          }
        ],
        footer: {
          text: 'Note: OpenAI Whisper API required for speech recognition'
        }
      };

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      logger.error('Failed to enable voice commands:', error);
      await interaction.editReply('Failed to enable voice commands. Make sure the bot has proper permissions and OpenAI API key is configured.');
    }
  }

  private async handleNoVoiceCommand(interaction: CommandInteraction): Promise<void> {
    if (!this.bot.isVoiceCommandsEnabled()) {
      await interaction.editReply('Voice commands are not enabled on this bot.');
      return;
    }

    if (!interaction.guildId) {
      await interaction.editReply('This command can only be used in a server!');
      return;
    }

    try {
      const wasActive = this.bot.isVoiceCommandsActive(interaction.guildId);
      
      if (!wasActive) {
        await interaction.editReply('Voice commands are not currently active in this server.');
        return;
      }

      await this.bot.disableVoiceCommands(interaction.guildId);
      
      const embed = {
        title: '🔇 Voice Commands Disabled',
        color: 0xff0000,
        description: 'Voice commands have been disabled for this server.\n\nUse `/voice` in a voice channel to re-enable them.',
        footer: {
          text: 'Regular slash commands continue to work normally'
        }
      };

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      logger.error('Failed to disable voice commands:', error);
      await interaction.editReply('Failed to disable voice commands.');
    }
  }

  private formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
}
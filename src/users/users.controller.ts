import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Query,
  ParseIntPipe,
  UseGuards,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
} from '@nestjs/swagger';
import { UsersService } from './users.service';
import { UserMapper } from './mapper/user.mapper';
import { UserResponse } from './response/user.response';
import { User } from './entity/user.entity';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import { EventsService } from '../events/events.service';
import { EventFiltersDto } from '../events/dto/event-filters.dto';
import { PaginatedEventResponse } from '../events/response/event.response';

@ApiTags('Users')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('api/users')
export class UsersController {
  constructor(
    private readonly usersService: UsersService,
    private readonly eventsService: EventsService,
  ) {}

  @Get('profile')
  @ApiOperation({ summary: 'Get the currently authenticated user' })
  @ApiResponse({ status: 200, type: UserResponse })
  getProfile(@CurrentUser() user: User): UserResponse {
    return UserMapper.toUserResponse(user);
  }

  @Get('favorites')
  @ApiOperation({ summary: "Get the current user's favorite events" })
  @ApiResponse({ status: 200, type: PaginatedEventResponse })
  async getFavorites(
    @CurrentUser() user: User,
    @Query() query: EventFiltersDto,
  ): Promise<PaginatedEventResponse> {
    return this.eventsService.findAll(query, user.favoriteEventIds ?? []);
  }

  @Post('favorites/:eventId')
  @ApiOperation({ summary: 'Add an event to the current user favorites' })
  @ApiParam({ name: 'eventId', description: 'Event ID' })
  @ApiResponse({ status: 201, type: UserResponse })
  @ApiResponse({ status: 404, description: 'Event not found' })
  async addFavorite(
    @CurrentUser() user: User,
    @Param('eventId', ParseIntPipe) eventId: number,
  ): Promise<UserResponse> {
    const updated = await this.usersService.addFavorite(user.id, eventId);
    return UserMapper.toUserResponse(updated);
  }

  @Delete('favorites/:eventId')
  @ApiOperation({ summary: 'Remove an event from the current user favorites' })
  @ApiParam({ name: 'eventId', description: 'Event ID' })
  @ApiResponse({ status: 200, type: UserResponse })
  async removeFavorite(
    @CurrentUser() user: User,
    @Param('eventId', ParseIntPipe) eventId: number,
  ): Promise<UserResponse> {
    const updated = await this.usersService.removeFavorite(user.id, eventId);
    return UserMapper.toUserResponse(updated);
  }
}

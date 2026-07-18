import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { User } from './entity/user.entity';
import { EventsService } from '../events/events.service';

@Injectable()
export class UsersService {
  constructor(
    @InjectRepository(User)
    private usersRepository: Repository<User>,
    private eventsService: EventsService,
  ) {}

  async findByEmail(email: string): Promise<User | null> {
    return this.usersRepository.findOne({ where: { email } });
  }

  async findById(id: number): Promise<User | null> {
    return this.usersRepository.findOne({ where: { id } });
  }

  async create(data: {
    email: string;
    passwordHash: string;
    firstName: string;
    lastName: string;
  }): Promise<User> {
    const user = this.usersRepository.create({
      ...data,
      favoriteEventIds: [],
    });
    return this.usersRepository.save(user);
  }

  private async getUserOrThrow(userId: number): Promise<User> {
    const user = await this.findById(userId);
    if (!user) {
      throw new NotFoundException(`User with ID ${userId} not found`);
    }
    return user;
  }

  async addFavorite(userId: number, eventId: number): Promise<User> {
    const user = await this.getUserOrThrow(userId);

    const event = await this.eventsService.findOne(eventId);
    if (!event) {
      throw new NotFoundException(`Event with ID ${eventId} not found`);
    }

    const favorites = user.favoriteEventIds ?? [];
    if (!favorites.includes(eventId)) {
      user.favoriteEventIds = [...favorites, eventId];
      await this.usersRepository.save(user);
    }

    return user;
  }

  async removeFavorite(userId: number, eventId: number): Promise<User> {
    const user = await this.getUserOrThrow(userId);

    const favorites = user.favoriteEventIds ?? [];
    user.favoriteEventIds = favorites.filter((id) => id !== eventId);
    await this.usersRepository.save(user);

    return user;
  }
}

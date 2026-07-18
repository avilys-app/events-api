import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Event } from './entity/event.entity';
import { PaginatedEventResponse } from './response/event.response';
import { EventMapper } from './mapper/event.mapper';
import { EventFiltersDto } from './dto/event-filters.dto';

@Injectable()
export class EventsService {
  constructor(
    @InjectRepository(Event)
    private eventsRepository: Repository<Event>,
  ) {}

  async findAll(
    filters: EventFiltersDto = {},
    restrictToIds?: number[],
  ): Promise<PaginatedEventResponse> {
    const page = filters.page || 1;
    const pageSize = filters.pageSize || 10;
    const skip = (page - 1) * pageSize;

    // When restricting to a specific set of ids (e.g. a user's favorites),
    // an empty set can never match, so short-circuit with an empty page.
    if (restrictToIds && restrictToIds.length === 0) {
      return { data: [], page, pageSize, total: 0 };
    }

    const query = this.eventsRepository.createQueryBuilder('event');

    if (restrictToIds) {
      query.andWhere('event.id IN (:...ids)', { ids: restrictToIds });
    }

    if (filters.category) {
      query.andWhere('event.category = :category', {
        category: filters.category,
      });
    }

    if (filters.location) {
      const locations = Array.isArray(filters.location)
        ? filters.location
        : (filters.location as string)
            .split(',')
            .map((loc) => loc.trim())
            .filter((loc) => loc.length > 0);

      if (locations.length > 0) {
        const locationConditions = locations
          .map(
            (_, index) =>
              `(event.city ILIKE :location${index} OR event.address ILIKE :location${index})`,
          )
          .join(' OR ');

        const locationParams = {};
        locations.forEach((loc, index) => {
          locationParams[`location${index}`] = `%${loc}%`;
        });

        query.andWhere(`(${locationConditions})`, locationParams);
      }
    }

    if (filters.startDate) {
      query.andWhere(
        '(event.startTime >= :startDate OR event.startTime IS NULL)',
        {
          startDate: filters.startDate,
        },
      );
    }

    if (filters.endDate) {
      const endOfDay = new Date(filters.endDate);
      endOfDay.setHours(23, 59, 59, 999);
      query.andWhere(
        '(event.startTime <= :endDate OR event.startTime IS NULL)',
        {
          endDate: endOfDay,
        },
      );
    }

    if (filters.search) {
      query.andWhere('unaccent(event.title) ILIKE unaccent(:search)', {
        search: `%${filters.search}%`,
      });
    }

    if (filters.hideExpired === 'true') {
      const today = new Date().toISOString().split('T')[0];
      query.andWhere('DATE(event.startTime) >= :today', { today });
    }

    if (filters.priceFrom !== undefined) {
      if (filters.priceFrom === 0) {
        query.andWhere(
          '(event.tickerUrl IS NULL AND event.priceFrom IS NULL AND event.priceTo IS NULL AND event.ticketPurchaseNote IS NULL AND (event.description IS NULL OR event.description NOT ILIKE :kaina)) OR (COALESCE(event.priceFrom, 0) >= :priceFrom)',
          {
            priceFrom: filters.priceFrom,
            kaina: '%kaina%',
          },
        );
      } else {
        query.andWhere('COALESCE(event.priceFrom, 0) >= :priceFrom', {
          priceFrom: filters.priceFrom,
        });
      }
    }

    if (filters.priceTo !== undefined) {
      if (filters.priceFrom === 0) {
        // Include free events when filtering from price 0
        query.andWhere(
          '(event.tickerUrl IS NULL AND event.priceFrom IS NULL AND event.priceTo IS NULL AND event.ticketPurchaseNote IS NULL AND (event.description IS NULL OR event.description NOT ILIKE :kaina)) OR (COALESCE(event.priceFrom, 0) <= :priceTo)',
          { priceTo: filters.priceTo, kaina: '%kaina%' },
        );
      } else {
        query.andWhere('COALESCE(event.priceFrom, 0) <= :priceTo', {
          priceTo: filters.priceTo,
        });
      }
    }

    if (filters.free === 'true') {
      query.andWhere(
        'event.tickerUrl IS NULL AND event.priceFrom IS NULL AND event.priceTo IS NULL AND event.ticketPurchaseNote IS NULL AND (event.description IS NULL OR event.description NOT ILIKE :kaina)',
        { kaina: '%kaina%' },
      );
    }

    const orderByColumn = filters.orderBy || 'startTime';
    const orderDirection = filters.orderDirection || 'DESC';
    const orderByMap = {
      startTime: 'event.startTime',
      title: 'event.title',
      popularityCounter: 'event.popularityCounter',
      price: 'COALESCE(event.priceFrom, 0)',
    };

    if (orderByColumn === 'price') {
      const hasPriceFilter =
        filters.priceFrom !== undefined || filters.priceTo !== undefined;

      // When price filter is active, always push free events to the bottom
      // When no price filter: DESC pushes free to bottom, ASC pushes free to top
      const freeEventsSortDirection =
        hasPriceFilter || orderDirection === 'DESC' ? 'ASC' : 'DESC';

      query.orderBy(
        `CASE WHEN event.tickerUrl IS NULL AND event.priceFrom IS NULL AND event.priceTo IS NULL AND event.ticketPurchaseNote IS NULL AND (event.description IS NULL OR event.description NOT ILIKE '%kaina%') THEN 1 ELSE 0 END`,
        freeEventsSortDirection,
      );

      // Push events with priceFrom=null AND not free to the end
      query.addOrderBy(
        `CASE WHEN event.priceFrom IS NULL AND NOT (event.tickerUrl IS NULL AND event.priceFrom IS NULL AND event.priceTo IS NULL AND event.ticketPurchaseNote IS NULL AND (event.description IS NULL OR event.description NOT ILIKE '%kaina%')) THEN 1 ELSE 0 END`,
        'ASC',
      );

      // Then order by price
      query.addOrderBy(orderByMap[orderByColumn], orderDirection);
    } else {
      query.orderBy(orderByMap[orderByColumn], orderDirection);
    }

    const [events, total] = await query
      .skip(skip)
      .take(pageSize)
      .getManyAndCount();

    const eventResponses = EventMapper.toEventResponseArray(events);

    return {
      data: eventResponses,
      page,
      pageSize,
      total,
    };
  }

  async findOne(id: number): Promise<Event> {
    return this.eventsRepository.findOne({ where: { id } });
  }

  async updatePopularityCounter(id: number): Promise<void> {
    await this.eventsRepository
      .createQueryBuilder()
      .update(Event)
      .set({ popularityCounter: () => 'popularity_counter + 1' })
      .where('id = :id', { id })
      .execute();
  }
}

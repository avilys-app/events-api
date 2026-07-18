import { ApiProperty } from '@nestjs/swagger';

export class UserResponse {
  @ApiProperty({ description: 'Unique identifier for the user' })
  id: number;

  @ApiProperty({ description: 'User email address' })
  email: string;

  @ApiProperty({ description: 'User first name' })
  firstName: string;

  @ApiProperty({ description: 'User last name' })
  lastName: string;

  @ApiProperty({
    description: 'IDs of events the user has favorited',
    type: [Number],
  })
  favoriteEventIds: number[];

  @ApiProperty({ description: 'When the user was created' })
  createdAt: Date;
}

export class AuthResponse {
  @ApiProperty({ description: 'JWT access token' })
  accessToken: string;

  @ApiProperty({ type: UserResponse, description: 'The authenticated user' })
  user: UserResponse;
}

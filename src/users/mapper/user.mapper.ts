import { User } from '../entity/user.entity';
import { UserResponse } from '../response/user.response';

export class UserMapper {
  static toUserResponse(user: User): UserResponse {
    const userResponse = new UserResponse();
    userResponse.id = user.id;
    userResponse.email = user.email;
    userResponse.firstName = user.firstName;
    userResponse.lastName = user.lastName;
    userResponse.favoriteEventIds = user.favoriteEventIds ?? [];
    userResponse.createdAt = user.createdAt;

    return userResponse;
  }
}

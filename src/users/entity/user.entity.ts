import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'text', unique: true, nullable: false })
  email: string;

  @Column({ name: 'password_hash', type: 'text', nullable: false })
  passwordHash: string;

  @Column({ name: 'first_name', type: 'text', nullable: false })
  firstName: string;

  @Column({ name: 'last_name', type: 'text', nullable: false })
  lastName: string;

  @Column({
    name: 'favorite_event_ids',
    type: 'int',
    array: true,
    default: [],
  })
  favoriteEventIds: number[];

  @CreateDateColumn({ name: 'created_at', type: 'timestamp' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp' })
  updatedAt: Date;
}

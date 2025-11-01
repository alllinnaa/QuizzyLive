-- Створення таблиці вікторин
create table if not exists public.quizzes (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Тригер для автозаповнення updated_at
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_quizzes_updated_at on public.quizzes;
create trigger set_quizzes_updated_at
before update on public.quizzes
for each row execute function public.set_updated_at();

-- Таблиця питань (4 відповіді + індекс правильної)
create table if not exists public.questions (
  id uuid primary key default gen_random_uuid(),
  quiz_id uuid not null references public.quizzes(id) on delete cascade,
  question_text text not null,
  answers jsonb not null check (
    jsonb_typeof(answers) = 'array' and jsonb_array_length(answers) = 4
  ),
  correct_answer smallint not null check (correct_answer between 0 and 3),
  position int not null default 0
);

create index if not exists idx_questions_quiz on public.questions(quiz_id);
create index if not exists idx_questions_position on public.questions(position);

-- (За потреби) Політики RLS — для продакшену налаштуйте під ваші JWT-ролі
alter table public.quizzes enable row level security;
alter table public.questions enable row level security;

-- Дозволити сервіс-ролі все (service role key обходить RLS). Для анонімного доступу додайте політики.
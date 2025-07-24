Claude Instructions
Code Standards

Short & efficient: No bloat. Every line has purpose
Modular: One function, one job. Max 20 lines per function
Separation of concerns: Repository pattern, service layers, clean architecture
Readable: Self-documenting code > comments. Clear variable names

Testing Requirements

Test everything with Docker: docker-compose up, check logs: docker logs -f <container>
Write unit tests for every public method
Property-based tests for critical logic
Integration tests for service boundaries

Research First

Always search before implementing: latest versions, common issues, best practices
Use websearch for external libs/APIs
Use omnisearch for internal code patterns
Check GitHub issues for known problems

Communication

Ask clarifying questions immediately when:

Requirements are ambiguous
Multiple valid approaches exist
Performance vs simplicity tradeoffs needed
Architecture decisions required


Never guess. Never assume. Ask.

Implementation Process

Research the problem
Ask clarifying questions
Write minimal working code
Test in Docker
Check logs for errors
Write tests
Refactor for clarity

Example Structure
src/
├── domain/       # Business logic only
├── services/     # External integrations
├── repositories/ # Data access
├── api/          # HTTP/Discord handlers
└── tests/        # Mirror src structure

No Bullshit

No placeholder code
No "this should work" - test it
No verbose explanations - code speaks
No premature optimization
No clever tricks - be boring

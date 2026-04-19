## ADDED Requirements

### Requirement: Root URL shows Django welcome page
The root URL ("/") SHALL display Django's built-in welcome page ("The install worked successfully!") in all example projects. This SHALL be achieved by removing the `static()` media URL patterns so Django's default-urlconf detection applies.

#### Scenario: User visits root URL
- **WHEN** a user makes a GET request to "/"
- **THEN** the server responds with Django's default welcome page (HTTP 200)

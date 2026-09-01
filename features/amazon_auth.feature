Feature: User Authentication & Desktop Session Persistence
  As a user
  I want to remain logged in securely on desktop browsers
  So that I do not need to re-enter credentials constantly

  @auth @desktop @login
  Scenario: Login successfully with valid credentials on desktop
    Given I am on the login page
    When I enter valid email and password
    Then I should be redirected to user dashboard
    And a valid session token should be stored in cookies

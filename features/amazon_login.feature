Feature: Account Login on Amazon
  As a returning Amazon customer
  I want to sign in to my account
  So that I can access my orders, cart, and personalized recommendations

  Background:
    Given I am on the Amazon sign-in page

  Scenario: Successful login with valid credentials
    When I enter a registered email address
    And I click "Continue"
    And I enter the correct password
    And I click "Sign-In"
    Then I should be redirected to the Amazon homepage
    And I should see my account name in the top navigation bar

  Scenario: Login fails with an incorrect password
    When I enter a registered email address
    And I click "Continue"
    And I enter an incorrect password
    And I click "Sign-In"
    Then I should see an error message indicating the password is incorrect
    And I should remain on the sign-in page

  Scenario: Login fails with an unregistered email address
    When I enter an email address that has no associated Amazon account
    And I click "Continue"
    Then I should see a prompt to create a new account
    And I should not be able to proceed to the password step

  Scenario: User can navigate to password reset flow
    When I enter a registered email address
    And I click "Continue"
    And I click "Forgot password?"
    Then I should be taken to the password recovery page
    And I should see an option to receive a reset code via email or SMS

  Scenario: Account locks out after repeated failed login attempts
    Given I have failed to log in 5 times in a row with an incorrect password
    When I attempt to log in again with any password
    Then I should see a message indicating my account is temporarily locked
    And I should see guidance on how to unlock or recover my account

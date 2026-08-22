Feature: Product Search on Amazon
  As a shopper on Amazon
  I want to search for products using the search bar
  So that I can quickly find items I want to buy

  Background:
    Given I am on the Amazon homepage

  Scenario: Search for a product using a valid keyword
    When I enter "wireless headphones" into the search bar
    And I click the search icon
    Then I should see a list of search results related to "wireless headphones"
    And the results page title should contain "wireless headphones"

  Scenario: Search returns no results for a nonsensical query
    When I enter "zzxxqqnonexistentproduct123" into the search bar
    And I click the search icon
    Then I should see a "no results found" message
    And I should see suggestions for alternative searches

  Scenario: Search bar autocomplete suggestions appear while typing
    When I start typing "lapt" into the search bar
    Then I should see a dropdown list of autocomplete suggestions
    And each suggestion should contain the text "lapt"

  Scenario Outline: Filter search results by category
    When I enter "<keyword>" into the search bar
    And I click the search icon
    And I select the "<category>" department filter
    Then all displayed results should belong to the "<category>" category

    Examples:
      | keyword    | category           |
      | headphones | Electronics         |
      | novel      | Books                |
      | sneakers   | Fashion              |

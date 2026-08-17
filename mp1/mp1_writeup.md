# MP1 Write-up: Prompt Strategy Comparison

## 1. Which strategy won, and on what dimension?

Few-shot is the overall winner because it achieved perfect accuracy (3.00/3) and a perfect judge score (25/25), while also having the lowest total cost among the four strategies

## 2. What surprised me?

The accuracy of Few shot prompt over all other prompts has surprised me. I have initially didn't used TOOLS in the llm request. The output for each strategy is different and not consistent. But by using tools , the accuracy is increased , and parsing issues are resolved by using tools.

## 3. Which strategy would I use for my capstone domain?

For my capstone project, i might use few shot prompt.

## 4. What would I try with another day?

I would expand the golden dataset to  40 examples and include more ambiguous cases, missing values,  Second, I would compare several prompt revisions within the winning strategy while keeping the model and temperature fixed. 

#  Maximum Subarray Sum 
'''
def maxsubarraysum(arr):
    sum = 0
    maxi = float('-inf')

    for num in arr:
        sum += num

        if sum > maxi:
            maxi = sum

        if sum < 0:
            sum = 0

    return maxi


# Example usage
arr = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
result = maxsubarraysum(arr)
print("Maximum subarray sum is:", result)

'''

#-----------------------------------------------------------------------------------------------------
# number to array of digits
'''
num = 12345 

arr = []

while num > 0:
    digit = num % 10
    arr.append(digit)
    num //= 10

arr.reverse()
print(arr)
'''

#-----------------------------------------------------------------------------------------------------

# num = 12345
#🎯 Task:
#Convert the number into an array of digits.
#Reverse the array.
#Convert it back into a number.
# ✅ Expected Output: 54321
'''
num = 12345

arr = []

while num > 0:
    digit = num % 10
    arr.append(digit)
    num //= 10

reversed_num = 0

for digit in arr:
    reversed_num = reversed_num * 10 + digit

print(reversed_num)
'''

#-----------------------------------------------------------------------------------------------------
# Given : num = 12030
# Expected Output: 3021

'''
num = 12030
arr = []

while num > 0:
    digit = num % 10
    arr.append(digit)
    num //= 10

reversed_num = 0

for digit in arr:
        reversed_num = reversed_num * 10 + digit

print(reversed_num)
'''

# 03021 → Python stores as 3021
# Leading zero doesn't matter in integers.
# And above if digit != 0: will remove all zeros , not only leading zeros but also zeros in between. 
#  So we should not use that condition 
#----------------------------------------------------------------------------------------------------------------------

# Move all zeros to the end of the array while mainatining the order of non-zero elements
'''
def moveallzerostoend(arr):

    n = len(arr)

    L = 0 
    R = 1 

    while R < n:
        if arr[L] == 0 and arr[R] != 0:
            arr[L], arr[R] = arr[R] , arr[L]
            L += 1
            R += 1

        elif arr[L] == 0 and arr[R] == 0:
            R += 1
        
        else:
            L += 1
            R += 1


# Example usage 
arr = [0, 1, 0, 3, 12]
moveallzerostoend(arr)
print(arr)
'''

#------------------------------------------------------------------------------------------------------------------
'''
def moveallzerostoend(arr):
    insert_pos = 0

    for i in range(len(arr)):
        if arr[i] != 0:
            arr[insert_pos], arr[i] = arr[i], arr[insert_pos]
            insert_pos += 1


arr = [0, 1, 0, 3, 12]
moveallzerostoend(arr)
print(arr)
'''
#------------------------------------------------------------------------------------------------------------------
'''
# Two Sum 
def twoSum(arr, target):

    n = len(arr)

    for i in range(n):
        for j in range(i+1, n):
            if arr[i] + arr[j] == target:
                return [i,j]
    
    return []


# example usage
arr = [2,7,11,15]
target = 17
print(twoSum(arr, target))
'''

#-------------------------------------------------------------------------------------

# Two Sum Problem using Hash Map

def twoSum(arr, target):

    # step 1 : create empty dictionary
    lookup = dict()

    # step 2 : loop thorugh array 
    i = 0
    while i < len(arr):

        # step 3 : take current number
        current_number = arr[i]

        # step 4 : calculate what number we need 
        needed_number = target - current_number

        # step 5 : check if needed number is in dictionary
        if needed_number in lookup:

            # get index of needed number
            index_of_needed = lookup[needed_number]

            # Return both indices
            result = [index_of_needed, i]
            return result
        
        # step 6 : if not found , store current number with index
        lookup[current_number] = i

        # step 7 : move to next number
        i = i + 1

    # step 8 : if no pair found 
    return []


# example usage 
arr = [2,7,11,15]
target = 17
print(twoSum(arr, target))








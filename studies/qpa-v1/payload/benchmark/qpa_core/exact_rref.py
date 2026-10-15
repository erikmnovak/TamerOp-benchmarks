"""Exact reference elimination that skips zeros in sparse bar differentials.

This is validator-only Python arithmetic, independent of both native tools.
It returns the same dense RREF and pivot convention as the original oracle.
"""
from fractions import Fraction

def rref(matrix,field,ncols=None):
    prime=None if field=='QQ' else int(field[1:])
    def scalar(x):
        q=Fraction(x)
        return q if prime is None else q.numerator*pow(q.denominator%prime,-1,prime)%prime
    n=len(matrix[0]) if matrix else (ncols or 0)
    assert all(len(row)==n for row in matrix)
    A=[{j:a for j,x in enumerate(row) if (a:=scalar(x))} for row in matrix]
    pivot=0;columns=[]
    for c in range(n):
        i=next((i for i in range(pivot,len(A)) if c in A[i]),None)
        if i is None:continue
        A[pivot],A[i]=A[i],A[pivot]
        inv=1/A[pivot][c] if prime is None else pow(A[pivot][c],-1,prime)
        row={j:(x*inv if prime is None else x*inv%prime) for j,x in A[pivot].items()};A[pivot]=row
        for i,R in enumerate(A):
            if i==pivot or c not in R:continue
            a=R[c]
            for j,y in row.items():
                x=R.get(j,0)-a*y
                if prime is not None:x%=prime
                if x:R[j]=x
                else:R.pop(j,None)
        columns.append(c);pivot+=1
        if pivot==len(A):break
    zero=Fraction(0) if prime is None else 0
    return [[row.get(j,zero) for j in range(n)] for row in A],columns

#!/bin/bash


for i  in  $(cat scannerlist); do
echo $i
    mkdir $i
    pamac search $i | grep "^ " > $i/description
done



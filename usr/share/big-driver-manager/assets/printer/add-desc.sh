#!/bin/bash


for i  in  $(cat printlist); do
echo $i
    mkdir $i
    pamac search $i | grep "^ " > $i/description
done



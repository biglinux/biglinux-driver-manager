#!/usr/bin/env bash

for i in $(ls); do
	pamac search $(cat $i/pkg) | grep "^ " > $i/description
done

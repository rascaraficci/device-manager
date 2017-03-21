#!/bin/bash
devicemanager_img="jenkins/devicemanager:$(git log --pretty=format:'%h' -1)"

iotagent_docker="iotagent-devm-jenkins"
devicemanager_docker="devicemanager-devm-jenkins"
mosquitto_docker="mosquitto-devm-jenkins"
orion_docker="orion-devm-jenkins"
mongodb_docker="mongodb-devm-jenkins"

iotagent_ip=""
devicemanager_ip=""
orion_ip=""
mosquitto_ip=""
mongodb_ip=""
max_tries=5
wait_time=10

docker="sudo docker"
curl="curl -sS"

function ping_host {
    local endpoint=$1
    local host=$2

    echo "Checking availability of ${host} by requesting ${endpoint}"
    tries=0
    ${curl} -X GET ${endpoint}
    while [ $? != 0 -a ${tries} -lt ${max_tries} ]; do
        echo "${host} is not yet ready."
        sleep ${wait_time}
        let tries=${tries}+1
        ${curl} -X GET ${endpoint}
    done;
    if [ ${tries} -eq ${max_tries} -a $? != 0 ]; then
        echo "${host} did not came up"
        return 1
    else
        echo "${host} is up!"
        return 0
    fi
}

function ping_hosts {
    echo "Checking services availability" 

    ping -c 1 ${mongodb_ip}
    echo "Checking mongodb accessibility"
    mongo ${mongodb_ip} --eval 'db.collection'
    if [ $? -ne 0 ]; then
        return 1
    fi

    ping -c 1 ${devicemanager_ip}
    ping_host "http://${devicemanager_ip}:5000/device" "Device manager"
    if [ $? -ne 0 ]; then
        return 1
    fi

    ping -c 1 ${orion_ip}
    ping_host "http://${orion_ip}:1026/NGSI10" "Orion"
    if [ $? -ne 0 ]; then
        return 1
    fi

    ping -c 1 ${iotagent_ip}
    ping_host "http://${iotagent_ip}:4041/iot/devices" "iotagent"
    if [ $? -ne 0 ]; then
        return 1
    fi
}

function ridiculously_simple_test {
    # Create service
    echo "Creating service"
    ans=$(${curl} -X POST -H "Fiware-Service: devm" -H "Fiware-ServicePath: /" -H "Content-Type: application/json" -H "Cache-Control: no-cache" -d '{
            "services": [
            {
                "resource": "/devm",
                "apikey": "device-api",
                "type": "device"
            }
            ]
        }' http://${iotagent_ip}:4041/iot/services)
    echo ${ans} | python -c "
import sys;
import json;
text=input()
print('{}'.format(text))
if len(text) != 0:
    exit(1)
exit(0)
"
    if [ $? != 0 ]; then
        echo "Could not create service"
        return 1
    else
        echo "Service created"
    fi

    # Device creation in devicemanager
    sleep ${wait_time}
    echo "Creating device"
    ans=$(${curl} -X POST http://${devicemanager_ip}:5000/device --header 'Content-Type:application/json' --data '{ "id" : "dev002", "label": "barometer-01", "protocol" : "mqtt", "attrs" : [ { "object_id": "pressure", "name": "Pressure", "type": "atm" } ] }')
    echo ${ans} | python -c "
import sys;
import json;
text=input()
print('{}'.format(text))
if text['message'] != 'ok':
    exit(1)
exit(0)
"
    if [ $? != 0 ]; then
        echo "Could not create device"
        return 1
    else
        echo "Device created"
    fi


    # MQTT data publication
    sleep ${wait_time}
    echo "Publishing new data"
    sudo docker exec ${mosquitto_docker} /usr/local/bin/mosquitto_pub -t /device-api/dev002/attrs -m '{"pressure":"1.04atm"}'

    # Reading new data in the broker
    sleep ${wait_time}
    echo "Checking on broker"
    ans=$(${curl} -X POST -H "Content-Type: application/json" -H "Accept: application/json" -H "Fiware-Service: devm" -H "Fiware-ServicePath: /" -d '{
        "entities": [
            {
                "isPattern": "false",
                "id": "barometer-01",
                "type": "device"
            }
        ]
    }' http://${orion_ip}:1026/NGSI10/queryContext)
    echo ${ans} | python -c "
import sys;
import json;
text=input()
print('{}'.format(text))
if len(text['contextResponses']) == 0:
    exit(1)
if len(text['contextResponses'][0]['contextElement']['attributes']) == 0:
    exit(1)
if text['contextResponses'][0]['contextElement']['attributes'][0]['value'] != '1.04atm':
    exit(1)
exit(0)
"
    if [ $? != 0 ]; then
        echo "Data was not updated"
        return 1
    else
        echo "Data updated correctly"
    fi
    return 0
}

function docker_start {
    echo "Starting all containers"
    docker-compose up -d
    sleep ${wait_time}
    $docker run -d --name ${devicemanager_docker} --net tests_default --link ${iotagent_docker}:iotagent --link ${mongodb_docker}:mongodb ${devicemanager_img}
}

function docker_stop {
    $docker kill ${devicemanager_docker}
    $docker rm ${devicemanager_docker}
    docker-compose down
}

function retrieve_ips {
    iotagent_ip=$($docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${iotagent_docker})
    devicemanager_ip=$($docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${devicemanager_docker})
    orion_ip=$($docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${orion_docker})
    mosquitto_ip=$($docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${mosquitto_docker})
    mongodb_ip=$($docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${mongodb_docker})

    echo "Services:"
    echo "iotagent: ${iotagent_ip}"
    echo "devicemanager: ${devicemanager_ip}"
    echo "orion: ${orion_ip}"
    echo "mongo: ${mongodb_ip}"
    echo "mosquitto: ${mosquitto_ip}"
}


if [ '$1' == 'ip' ]; then
    retrieve_ips
    exit 0
elif [ '$1' == 'test' ]; then
    retrieve_ips
    ping_hosts
    ridiculously_simple_test
    exit 0
fi

docker_stop
docker_start
retrieve_ips
ping_hosts
if [ $? -eq 0 ]; then
    ridiculously_simple_test
    docker_stop
    if [ $? -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
else
    echo "One of the mandatory services is not operational"
    exit 1
fi
exit 0

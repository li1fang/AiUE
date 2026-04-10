#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PMXEquipmentBlueprintLibrary.generated.h"

class AActor;
class UAnimationAsset;
class UPMXCharacterEquipmentComponent;
class UPMXEquipmentLoadoutAsset;
class USkeletalMesh;
class USkeletalMeshComponent;

UCLASS()
class AIUEPMXRUNTIME_API UPMXEquipmentBlueprintLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="PMXPipeline", meta=(DefaultToSelf="Actor"))
    static UPMXCharacterEquipmentComponent* FindOrAddEquipmentComponent(AActor* Actor);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline", meta=(DefaultToSelf="Actor"))
    static bool SetEquipmentAttachSocket(AActor* Actor, FName SocketName);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline", meta=(DefaultToSelf="Actor"))
    static USkeletalMeshComponent* EquipWeaponMesh(AActor* Actor, USkeletalMesh* WeaponMesh);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline", meta=(DefaultToSelf="Actor"))
    static USkeletalMeshComponent* EquipWeaponMeshToSocket(AActor* Actor, USkeletalMesh* WeaponMesh, FName SocketName);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline", meta=(DefaultToSelf="Actor"))
    static USkeletalMeshComponent* ApplyEquipmentLoadout(AActor* Actor, UPMXEquipmentLoadoutAsset* LoadoutAsset);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    static FPMXAnimationPoseEvaluationResult EvaluateAnimationPoseOnComponent(
        USkeletalMeshComponent* MeshComponent,
        UAnimationAsset* AnimationAsset,
        float SampleTimeSeconds,
        const TArray<FName>& ProbeBoneNames
    );
};
